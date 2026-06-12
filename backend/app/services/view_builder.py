from __future__ import annotations

from typing import Any

from app.data.catalog import FLOW_SCHEMA_VERSION, unknown_option
from app.services.document_service import DocumentService, document_service
from app.services.inquiry_service import InquiryService, inquiry_service
from app.services.slot_utils import label_for_field, slot_known, slot_value


class ViewBuilder:
    def __init__(
        self,
        documents: DocumentService = document_service,
        inquiries: InquiryService = inquiry_service,
    ) -> None:
        self.documents = documents
        self.inquiries = inquiries

    def envelope(self, case: dict[str, Any]) -> dict[str, Any]:
        view = self.build_view(case)
        return {
            "ok": True,
            "caseId": case["caseId"],
            "turnId": f"turn_{len(case['answers'])}",
            "view": view,
            "caseState": {
                "status": case["machineState"],
                "currentStep": view["type"],
                "progressStage": self.progress_stage(case["machineState"]),
            },
            "statePatch": {
                "slots": case["slots"],
                "answers": case["answers"],
                "documents": case["documents"],
                "inquiryTasks": case["inquiryTasks"],
                "completedDocumentIds": case["completedDocumentIds"],
                "questionLoop": case["questionLoop"],
                "flowState": case,
            },
            "meta": {
                "schemaVersion": FLOW_SCHEMA_VERSION,
                "source": "rules+ai-boundary",
                "fallback": case["ai"].get("intakeSource") != "llm",
                "warnings": case["ai"].get("warnings", []),
            },
        }

    def build_view(self, case: dict[str, Any]) -> dict[str, Any]:
        state = case["machineState"]
        if state == "NEEDS_INFO":
            return self.slot_question_view(case)
        if state == "DIAGNOSIS":
            return self.diagnosis_view(case)
        if state == "DOCUMENTS":
            return self.documents_view(case)
        if state == "INQUIRY":
            return self.inquiry_view(case)
        if state == "ANSWER_REVIEW":
            return self.answer_review_view(case)
        if state == "DASHBOARD":
            return self.dashboard_view(case)
        if state == "SUBMITTED":
            return self.submitted_view(case)
        return self.diagnosis_view(case)

    @staticmethod
    def slot_question_view(case: dict[str, Any]) -> dict[str, Any]:
        current = case["questionLoop"].get("current") or {}
        return {
            "type": "slot_question",
            "field": current.get("field"),
            "title": current.get("question") or "확인이 더 필요해요",
            "subtitle": current.get("why") or "",
            "inputMode": current.get("inputMode") or "free_text",
            "options": current.get("options") or [unknown_option()],
            "validationMessage": current.get("validationMessage") or "",
            "nextButtonLabel": "다음",
            "loop": {
                "totalAsked": case["questionLoop"]["totalAsked"],
                "maxTotalQuestions": case["questionLoop"]["maxTotalQuestions"],
                "plannedTotalQuestions": min(
                    case["questionLoop"]["maxTotalQuestions"],
                    len(case["questionLoop"].get("pendingQuestions") or []),
                ),
                "attemptsForField": case["questionLoop"]["attempts"].get(current.get("field"), 0),
                "maxAttemptsPerField": case["questionLoop"]["maxAttemptsPerField"],
            },
        }

    def diagnosis_view(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "diagnosis",
            "title": "준비 방향이 나왔어요",
            "headline": self.diagnosis_headline(case),
            "candidatePermits": case["candidatePermits"],
            "decisionBlocks": self.decision_blocks(case),
            "nextButtonLabel": "서류 보러가기",
        }

    def documents_view(self, case: dict[str, Any]) -> dict[str, Any]:
        next_label = "문의하기" if self.inquiries.has_open_inquiry(case) else "진행 상황 보기"
        return {
            "type": "documents",
            "title": "필요 서류를 준비해요",
            "documents": case["documents"],
            "completedDocumentIds": case["completedDocumentIds"],
            "nextButtonLabel": next_label,
        }

    def inquiry_view(self, case: dict[str, Any]) -> dict[str, Any]:
        task = next((item for item in case["inquiryTasks"] if item["status"] == "pending"), None)
        task = task or (case["inquiryTasks"][0] if case["inquiryTasks"] else None)
        return {
            "type": "inquiry",
            "title": "어떻게 문의할까요?",
            "mode": case.get("selectedInquiryChannel") or "channels",
            "task": task,
            "channels": [
                {"id": "phone", "title": "전화하기", "description": "번호로 바로 연결합니다."},
                {"id": "online", "title": "문안 복사", "description": "문의 글을 바로 쓸 수 있어요."},
                {"id": "visit", "title": "방문하기", "description": "창구와 준비물을 확인합니다."},
            ],
            "onlineDraft": self.inquiries.online_draft(case, task),
            "nextButtonLabel": "답변 기록하기",
        }

    @staticmethod
    def answer_review_view(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "answer_review",
            "title": "답변을 반영했어요",
            "analysis": case.get("lastAnswerAnalysis") or {},
            "nextButtonLabel": "계속하기",
        }

    def submitted_view(self, case: dict[str, Any]) -> dict[str, Any]:
        documents = sorted(case["documents"], key=lambda item: item["priority"])
        completed_ids = set(case["completedDocumentIds"])
        completed_count = len(completed_ids)
        total_count = len(documents)
        resolved_inquiries = len([task for task in case["inquiryTasks"] if task["status"] == "resolved"])
        total_inquiries = len(case["inquiryTasks"])
        completion_rate = 100 if total_count and completed_count >= total_count else round((completed_count / total_count) * 100) if total_count else 100

        return {
            "type": "submitted",
            "title": "서류 제출이 끝났어요",
            "subtitle": "준비한 서류와 문의 답변을 제출 완료 상태로 정리했어요.",
            "completionRate": completion_rate,
            "statusCards": [
                {"label": "서류", "value": f"{completed_count}/{total_count}"},
                {"label": "진행률", "value": f"{completion_rate}%"},
                {"label": "문의", "value": f"{resolved_inquiries}/{total_inquiries}" if total_inquiries else "없음"},
            ],
            "submittedDocuments": [
                {
                    "id": document["id"],
                    "title": document["title"],
                    "statusLabel": "완료" if document["id"] in completed_ids else "확인 필요",
                    "meta": f'우선순위 {document["priority"]} · 예상 소요 {document["perceivedDuration"]}',
                }
                for document in documents
            ],
            "nextNotes": [
                "접수번호나 방문 기록은 따로 보관하세요.",
                "추가 연락이 오면 진행 상황에 기록하세요.",
            ],
            "nextButtonLabel": "진행 상황 보기",
        }

    def dashboard_view(self, case: dict[str, Any]) -> dict[str, Any]:
        done_docs = len(case["completedDocumentIds"])
        total_docs = len(case["documents"])
        open_tasks = len([task for task in case["inquiryTasks"] if task["status"] == "pending"])
        return {
            "type": "dashboard",
            "title": "진행 상황",
            "summary": {
                "documents": f"{done_docs}/{total_docs}",
                "openInquiryTasks": open_tasks,
                "answeredQuestions": len(case["questionLoop"]["answeredFields"]),
                "unknownFields": len(case["questionLoop"]["unknownFields"]),
            },
            "sections": self.dashboard_sections(case),
            "nextActions": self.next_actions(case),
            "nextButtonLabel": self.dashboard_primary_label(case),
        }

    def decision_blocks(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        documents = case["documents"] or self.documents.build_documents(case)
        missing_required = self.required_unknown_fields(case)
        open_tasks = [task for task in case["inquiryTasks"] if task["status"] == "pending"]
        blocks = []
        ready_docs = [doc for doc in documents if doc["canPrepareBeforeInquiry"]]
        if ready_docs:
            blocks.append({
                "type": "ready_for_documents",
                "title": "지금 준비할 서류",
                "items": [doc["title"] for doc in ready_docs],
            })
        info_fields = [field for field in missing_required if field != "exact_address"]
        if info_fields:
            blocks.append({
                "type": "needs_user_info",
                "title": "더 확인할 것",
                "items": [label_for_field(field) for field in info_fields],
            })
        if open_tasks:
            blocks.append({
                "type": "needs_department_check",
                "title": "부서에 물어볼 것",
                "items": [task["title"] for task in open_tasks],
            })
        if "exact_address" in missing_required:
            blocks.append({
                "type": "needs_user_decision",
                "title": "먼저 정할 것",
                "items": ["주소가 있어야 건물과 관할 부서를 확인할 수 있어요."],
            })
        return blocks

    @staticmethod
    def required_unknown_fields(case: dict[str, Any]) -> list[str]:
        required = ["exact_address", "building_use"]
        return [field for field in required if not slot_known(case, field)]

    @staticmethod
    def diagnosis_headline(case: dict[str, Any]) -> str:
        location = slot_value(case, "location")
        activity = slot_value(case, "business_activity")
        if location and activity:
            return f"{location} {activity} 준비로 확인했어요."
        if activity:
            return f"{activity} 준비로 확인했어요."
        return "입력한 내용을 기준으로 정리했어요."

    def next_actions(self, case: dict[str, Any]) -> list[str]:
        actions = []
        if any(doc["status"] != "completed" for doc in case["documents"]):
            actions.append("남은 서류 체크")
        if self.inquiries.has_open_inquiry(case):
            actions.append("문의 답변 기록")
        if not actions:
            actions.append("제출 현황 확인")
        return actions

    def dashboard_sections(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        pending_documents = [
            document
            for document in case["documents"]
            if document["id"] not in case["completedDocumentIds"] and document["status"] != "completed"
        ]
        ready_documents = [document for document in pending_documents if document.get("canPrepareBeforeInquiry")]
        open_tasks = [task for task in case["inquiryTasks"] if task["status"] == "pending"]
        sections = []

        updates = self.dashboard_update_items(case)
        if updates:
            sections.append({
                "id": "updates",
                "title": "최근 업데이트",
                "subtitle": "새로 바뀐 내용입니다.",
                "icon": "refresh",
                "badge": f"{len(updates)}개",
                "items": updates,
            })

        next_items = []
        if open_tasks:
            next_items.append({
                "id": "continue-inquiry",
                "title": "문의 이어가기",
                "description": f'{open_tasks[0]["title"]}을 확인하세요.',
                "statusLabel": "문의",
                "tone": "pending",
                "meta": open_tasks[0]["reason"],
                "actionId": "inquiry",
            })
        if pending_documents:
            next_items.append({
                "id": "continue-documents",
                "title": "서류 이어가기",
                "description": f'{pending_documents[0]["title"]}부터 체크하세요.',
                "statusLabel": "서류",
                "tone": "pending",
                "meta": f'{len(pending_documents)}개 남음',
                "actionId": "documents",
            })
        if not next_items:
            next_items.append({
                "id": "ready-submit",
                "title": "제출 현황 보기",
                "description": "모든 서류가 완료됐어요.",
                "statusLabel": "완료",
                "tone": "done",
                "meta": "100%",
                "actionId": "submitted",
            })

        sections.append({
            "id": "next_actions",
            "title": "다음 할 일",
            "subtitle": "위 항목부터 진행하세요.",
            "icon": "list",
            "badge": f"{len(next_items)}개",
            "items": next_items,
        })

        sections.append({
            "id": "ready_documents",
            "title": "지금 준비할 서류",
            "subtitle": "바로 시작할 수 있어요.",
            "icon": "fileCheck",
            "badge": f"{len(ready_documents)}개",
            "empty": "새로 준비할 서류가 없어요.",
            "items": [
                {
                    "id": document["id"],
                    "title": document["title"],
                    "description": f'예상 소요 {document["perceivedDuration"]} · {document["reason"]}',
                    "statusLabel": "시작 가능",
                    "tone": "ready",
                    "meta": document.get("prerequisites", ""),
                    "actionId": "documents",
                }
                for document in ready_documents[:4]
            ],
        })
        return sections

    @staticmethod
    def dashboard_update_items(case: dict[str, Any]) -> list[dict[str, Any]]:
        analysis = case.get("lastAnswerAnalysis") or {}
        updates = []
        if analysis.get("answerSummary"):
            updates.append({
                "id": "answer-summary",
                "title": "답변 반영 완료",
                "description": analysis["answerSummary"],
                "statusLabel": "업데이트",
                "tone": "updated",
                "meta": "방금 반영",
            })
        if analysis.get("resolvedItems"):
            updates.append({
                "id": "resolved-items",
                "title": "해결됨",
                "description": ", ".join(str(item) for item in analysis["resolvedItems"]),
                "statusLabel": "해결",
                "tone": "done",
                "meta": f'{len(analysis["resolvedItems"])}개',
            })
        if analysis.get("newMissingFields"):
            updates.append({
                "id": "new-missing-fields",
                "title": "새 확인 항목",
                "description": ", ".join(label_for_field(str(field)) for field in analysis["newMissingFields"]),
                "statusLabel": "새 항목",
                "tone": "new",
                "meta": f'{len(analysis["newMissingFields"])}개',
            })
        if analysis.get("newInquiryTasks"):
            updates.append({
                "id": "new-inquiry-tasks",
                "title": "새 문의",
                "description": ", ".join(task["title"] for task in analysis["newInquiryTasks"]),
                "statusLabel": "새 문의",
                "tone": "new",
                "meta": f'{len(analysis["newInquiryTasks"])}개',
            })
        return updates

    def dashboard_primary_label(self, case: dict[str, Any]) -> str:
        if self.inquiries.has_open_inquiry(case):
            return "문의 이어가기"
        if any(doc["status"] != "completed" for doc in case["documents"]):
            return "서류 이어가기"
        return "제출 현황 보기"

    @staticmethod
    def progress_stage(machine_state: str) -> str:
        if machine_state in {"NEEDS_INFO", "UNDERSTAND", "INTAKE"}:
            return "intake"
        if machine_state == "DIAGNOSIS":
            return "diagnosis"
        if machine_state == "DOCUMENTS":
            return "documents"
        if machine_state in {"INQUIRY", "ANSWER_REVIEW"}:
            return "inquiry"
        if machine_state == "SUBMITTED":
            return "submitted"
        return "dashboard"


view_builder = ViewBuilder()
