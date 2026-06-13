from __future__ import annotations

from typing import Any

from app.models.case_factory import new_case
from app.repositories.case_repository import InMemoryCaseRepository, case_repository
from app.services.document_service import DocumentService, document_service
from app.services.intake_agent import IntakeAgent, intake_agent
from app.services.minju_pipeline_bridge import MinjuPipelineBridge, minju_pipeline_bridge
from app.services.question_planner import QuestionPlanner, question_planner
from app.services.slot_utils import as_list, now_iso, slot_value
from app.services.view_builder import ViewBuilder, view_builder


class FlowInputError(ValueError):
    pass


FOLLOWUP_SKIP_FIELDS = {
    "area",
    "lease_contract",
    "hygieneTraining",
    "healthCertificate",
    "fireCertificate",
    "signboard_image",
}

FOLLOWUP_PRIORITY = [
    "liquor_sales",
    "manufacturing_or_simple_sale",
    "on_site_consumption",
    "condition_screening",
    "signboard_planned",
    "signboard_type",
    "signboard_size",
    "owner_consent",
    "outdoor_space_planned",
    "outdoor_location",
    "outdoor_area",
    "takeover_type",
]


class CaseFlowService:
    def __init__(
        self,
        repository: InMemoryCaseRepository = case_repository,
        intake: IntakeAgent = intake_agent,
        questions: QuestionPlanner = question_planner,
        documents: DocumentService = document_service,
        minju: MinjuPipelineBridge = minju_pipeline_bridge,
        views: ViewBuilder = view_builder,
    ) -> None:
        self.repository = repository
        self.intake = intake
        self.questions = questions
        self.documents = documents
        self.minju = minju
        self.views = views

    @property
    def cases(self) -> dict[str, dict[str, Any]]:
        return self.repository.cases

    def create_case(self, raw_text: str) -> dict[str, Any]:
        case = new_case(raw_text)
        self.minju.bootstrap(case)
        self.intake.understand(case, use_llm=(case.get("minjuDraft") or {}).get("status") != "ok")
        case["questionLoop"]["pendingQuestions"] = self.questions.build_question_plan(case)
        self.repository.add(case)
        case = self.questions.start_or_finish_question_loop(case)
        self.sync_minju_outputs(case)
        return case

    def apply_turn(self, case_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        case = self.repository.get(case_id)
        if not case:
            text = input_payload.get("text") or ""
            return self.create_case(text)

        input_type = input_payload.get("type")
        case["updatedAt"] = now_iso()

        if input_type == "slot_answer":
            if case["machineState"] != "NEEDS_INFO":
                raise FlowInputError("현재 단계에서는 질문 답변을 받을 수 없습니다.")
            self.questions.apply_slot_answer(case, input_payload)
            if case["questionLoop"].pop("retryCurrent", False):
                return case
            case = self.questions.start_or_finish_question_loop(case)
            self.sync_minju_outputs(case)
            return case

        if input_type == "action":
            return self.apply_action(case, input_payload.get("actionId", "primary"))

        if input_type == "document_toggle":
            self.ensure_documents_ready(case)
            document_id = input_payload.get("documentId")
            if document_id not in {document["id"] for document in case["documents"]}:
                raise FlowInputError("존재하지 않는 서류입니다.")
            self.documents.toggle_document(case, document_id, bool(input_payload.get("completed")))
            case["machineState"] = "DOCUMENTS"
            return case

        raise FlowInputError("지원하지 않는 입력입니다.")

    def apply_action(self, case: dict[str, Any], action_id: str) -> dict[str, Any]:
        state = case["machineState"]
        if action_id == "restart":
            return self.create_case("")
        if action_id == "documents":
            self.ensure_documents_ready(case)
            case["machineState"] = "DOCUMENTS"
            return case
        if action_id == "dashboard":
            self.ensure_documents_ready(case)
            case["machineState"] = "DASHBOARD"
            return case
        if action_id == "submitted":
            case["machineState"] = "SUBMITTED" if self.all_documents_completed(case) else "DASHBOARD"
            return case

        if state == "DIAGNOSIS":
            if self.start_minju_followup_if_needed(case):
                return case
            case["machineState"] = "CONFIRM_UNDERSTANDING"
            return case

        if state == "CONFIRM_UNDERSTANDING":
            if action_id == "edit_understanding":
                self.start_understanding_edit(case)
                return self.questions.start_or_finish_question_loop(case)
            case["understandingConfirmed"] = True
            self.ensure_documents_ready(case)
            case["machineState"] = "DOCUMENTS"
            return case

        if state == "DOCUMENTS":
            case["machineState"] = "DASHBOARD"
            return case

        if state == "INQUIRY":
            case["machineState"] = "DASHBOARD"
            return case

        if state == "ANSWER_REVIEW":
            return self.route_after_answer_review(case)

        if state == "DASHBOARD":
            if any(document["status"] != "completed" for document in case["documents"]):
                case["machineState"] = "DOCUMENTS"
                return case
            case["machineState"] = "SUBMITTED"
            return case

        if state == "SUBMITTED":
            case["machineState"] = "DASHBOARD"
            return case

        return case

    @staticmethod
    def all_documents_completed(case: dict[str, Any]) -> bool:
        documents = case.get("documents") or []
        completed_ids = set(case.get("completedDocumentIds") or [])
        return all(document["id"] in completed_ids or document.get("status") == "completed" for document in documents)

    def route_after_answer_review(self, case: dict[str, Any]) -> dict[str, Any]:
        analysis = case.get("lastAnswerAnalysis") or {}
        # 분석은 한 번만 소비한다. 비우지 않으면 ANSWER_REVIEW 재진입마다 같은
        # newMissingFields를 다시 처리해 후속 질문↔진단 사이를 무한 반복한다.
        case["lastAnswerAnalysis"] = {}
        followups = self.questions.followup_fields(case, analysis.get("newMissingFields") or [])
        if followups:
            self.questions.add_followup_questions(case, followups)
            return self.questions.start_or_finish_question_loop(case)
        if analysis.get("nextAction") == "documents":
            case["machineState"] = "DOCUMENTS" if not self.all_documents_completed(case) else "DASHBOARD"
            return case
        case["machineState"] = "DASHBOARD"
        return case

    def envelope(self, case: dict[str, Any]) -> dict[str, Any]:
        return self.views.envelope(case)

    def sync_minju_outputs(self, case: dict[str, Any]) -> None:
        if case["machineState"] != "DIAGNOSIS":
            return
        self.minju.sync(case)
        if (case.get("minjuIntake") or {}).get("status") == "ok":
            case["documents"] = self.documents.build_documents(case)
            case["inquiryTasks"] = []

    @staticmethod
    def ensure_documents_ready(case: dict[str, Any]) -> None:
        if not case.get("documents"):
            raise FlowInputError("아직 서류 단계로 이동할 수 없습니다.")

    def start_minju_followup_if_needed(self, case: dict[str, Any]) -> bool:
        fields = self.minju_followup_fields(case)
        asked = set(case.get("minjuFollowupAskedFields") or [])
        fields = [field for field in fields if field not in asked]
        if not fields:
            return False

        case["minjuFollowupAskedFields"] = sorted(asked.union(fields))
        case["questionLoop"]["maxTotalQuestions"] = max(
            case["questionLoop"]["maxTotalQuestions"],
            case["questionLoop"]["totalAsked"] + len(fields) + 1,
        )
        self.questions.add_followup_questions(case, fields)
        self.questions.start_or_finish_question_loop(case)
        return case["machineState"] == "NEEDS_INFO"

    def minju_followup_fields(self, case: dict[str, Any]) -> list[str]:
        summary = ((case.get("minjuIntake") or {}).get("summary") or {})
        judgement = summary.get("aiJudgement") or {}
        fields: list[str] = []
        for item in judgement.get("questionsToAsk") or []:
            for field in self.questions.fields_for_minju_item(case, item):
                if field not in fields:
                    fields.append(field)

        for field in self.questions.minju_missing_fields(case, buckets=("recommendedNext",)):
            if field not in fields:
                fields.append(field)

        graph = summary.get("requirementGraph") or {}
        for item in graph.get("missingInputs") or []:
            for field in self.questions.fields_for_minju_item(case, item):
                if field not in fields:
                    fields.append(field)

        fields.extend(self.condition_followup_fields(case))
        filtered = [
            field
            for field in self.questions.followup_fields(case, fields)
            if field not in FOLLOWUP_SKIP_FIELDS
        ]
        return self.sort_followup_fields(filtered)[:6]

    @staticmethod
    def condition_followup_fields(case: dict[str, Any]) -> list[str]:
        fields: list[str] = []
        if slot_value(case, "liquor_sales") in (None, "", "unknown"):
            fields.append("liquor_sales")
        if slot_value(case, "manufacturing_or_simple_sale") in (None, "", "unknown"):
            fields.append("manufacturing_or_simple_sale")
        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        if not conditions:
            fields.extend(["signboard_planned", "outdoor_space_planned"])
        if "signage_planned" in conditions or slot_value(case, "signboard_planned") is True:
            fields.extend(["signboard_type", "signboard_size", "owner_consent"])
        if "outdoor_space_planned" in conditions or slot_value(case, "outdoor_space_planned") is True:
            fields.extend(["outdoor_location", "outdoor_area", "owner_consent"])
        return fields

    @staticmethod
    def sort_followup_fields(fields: list[str]) -> list[str]:
        unique: list[str] = []
        for field in fields:
            if field not in unique:
                unique.append(field)
        order = {field: index for index, field in enumerate(FOLLOWUP_PRIORITY)}
        return sorted(unique, key=lambda field: (order.get(field, 999), unique.index(field)))

    def start_understanding_edit(self, case: dict[str, Any]) -> None:
        fields = [
            "exact_address",
            "business_activity",
            "liquor_sales",
            "manufacturing_or_simple_sale",
            "condition_screening",
        ]
        conditions = set(str(item) for item in (case.get("slots", {}).get("condition_screening", {}) or {}).get("value", []) or [])
        if "signage_planned" in conditions:
            fields.extend(["signboard_type", "signboard_size", "owner_consent"])
        if "outdoor_space_planned" in conditions:
            fields.extend(["outdoor_location", "outdoor_area", "owner_consent"])
        self.questions.add_edit_questions(case, fields)


flow_service = CaseFlowService()
