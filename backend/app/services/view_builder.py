from __future__ import annotations

from typing import Any

from app.data.catalog import FLOW_SCHEMA_VERSION, QUESTION_BANK, unknown_option
from app.services.document_service import DocumentService, document_service
from app.services.slot_utils import as_list, display_value_for_field, label_for_field, slot_known, slot_value


DISPLAY_QUESTION_SKIP_IDS = {
    "area",
    "area_if_known",
    "lease_contract",
    "hygieneTraining",
    "hygiene_training",
    "healthCertificate",
    "health_certificate",
    "fireCertificate",
    "fire_certificate",
    "signboard_image",
    "building_use",
}

ADDRESS_QUESTION_IDS = {
    "address",
    "base_address",
    "detailed_address",
    "detailed_address_for_building_check",
}

FLOOR_QUESTION_IDS = {"floor_unit", "floor_or_unit_if_known"}


class ViewBuilder:
    def __init__(
        self,
        documents: DocumentService = document_service,
    ) -> None:
        self.documents = documents

    def envelope(self, case: dict[str, Any]) -> dict[str, Any]:
        case["inquiryTasks"] = []
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
                "source": "rules+ai+graph-rag-boundary",
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
        if state == "CONFIRM_UNDERSTANDING":
            return self.understanding_review_view(case)
        if state == "DOCUMENTS":
            return self.documents_view(case)
        if state in {"INQUIRY", "ANSWER_REVIEW"}:
            case["machineState"] = "DASHBOARD"
            if not case.get("documents"):
                case["documents"] = self.documents.build_documents(case)
            return self.dashboard_view(case)
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
                    max(
                        case["questionLoop"]["totalAsked"],
                        len(case["questionLoop"].get("pendingQuestions") or []),
                    ),
                ),
                "attemptsForField": case["questionLoop"]["attempts"].get(current.get("field"), 0),
                "maxAttemptsPerField": case["questionLoop"]["maxAttemptsPerField"],
            },
        }

    def diagnosis_view(self, case: dict[str, Any]) -> dict[str, Any]:
        guidance = self.diagnosis_guidance(case)
        has_followup = bool(guidance.get("questionsToAsk"))
        return {
            "type": "diagnosis",
            "title": guidance.get("title") or "준비 방향이 나왔어요",
            "headline": guidance.get("headline") or self.diagnosis_headline(case),
            "guidance": guidance,
            "candidatePermits": case["candidatePermits"],
            "decisionBlocks": self.decision_blocks(case),
            "nextButtonLabel": "추가 정보 답하기" if has_followup else "이해한 내용 확인하기",
        }

    def documents_view(self, case: dict[str, Any]) -> dict[str, Any]:
        next_label = "진행 상황 보기"
        return {
            "type": "documents",
            "title": "필요 서류를 준비해요",
            "documents": case["documents"],
            "completedDocumentIds": case["completedDocumentIds"],
            "nextButtonLabel": next_label,
        }

    def understanding_review_view(self, case: dict[str, Any]) -> dict[str, Any]:
        guidance = self.diagnosis_guidance(case)
        return {
            "type": "understanding_review",
            "title": "이렇게 이해했어요",
            "subtitle": "맞으면 서류 준비 순서로 넘어가고, 다르면 지금 수정할 수 있어요.",
            "items": self.understanding_items(case),
            "apiItems": guidance.get("apiStatusItems") or [],
            "buildingItems": guidance.get("buildingItems") or [],
            "suitabilityTitle": guidance.get("suitabilityTitle") or "적합성 판단",
            "suitabilitySummary": guidance.get("suitabilitySummary") or guidance.get("summary") or "",
            "nextButtonLabel": "맞아요, 계속",
            "editButtonLabel": "수정할래요",
        }

    @staticmethod
    def understanding_items(case: dict[str, Any]) -> list[dict[str, str]]:
        fields = [
            "business_activity",
            "exact_address",
            "floor_unit",
            "area",
            "liquor_sales",
            "manufacturing_or_simple_sale",
            "condition_screening",
            "takeover_type",
            "lease_contract",
            "owner_consent",
            "signboard_type",
            "signboard_size",
            "outdoor_location",
            "outdoor_area",
        ]
        items: list[dict[str, str]] = []
        for field in fields:
            value = slot_value(case, field)
            if value in (None, "", [], "unknown"):
                continue
            items.append({
                "label": label_for_field(field),
                "value": display_value_for_field(field, value),
            })
        return items

    def submitted_view(self, case: dict[str, Any]) -> dict[str, Any]:
        documents = sorted(case["documents"], key=lambda item: item["priority"])
        completed_ids = set(case["completedDocumentIds"])
        completed_count = len(completed_ids)
        total_count = len(documents)
        completion_rate = 100 if total_count and completed_count >= total_count else round((completed_count / total_count) * 100) if total_count else 100

        return {
            "type": "submitted",
            "title": "서류 제출이 끝났어요",
            "subtitle": "준비한 서류를 제출 완료 상태로 정리했어요.",
            "completionRate": completion_rate,
            "statusCards": [
                {"label": "서류", "value": f"{completed_count}/{total_count}"},
                {"label": "진행률", "value": f"{completion_rate}%"},
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
        return {
            "type": "dashboard",
            "title": "진행 상황",
            "summary": {
                "documents": f"{done_docs}/{total_docs}",
                "answeredQuestions": len(case["questionLoop"]["answeredFields"]),
                "unknownFields": len(case["questionLoop"]["unknownFields"]),
            },
            "sections": self.dashboard_sections(case),
            "nextActions": self.next_actions(case),
            "nextButtonLabel": self.dashboard_primary_label(case),
        }

    def decision_blocks(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        has_minju_summary = bool(((case.get("minjuIntake") or {}).get("summary") or {}))
        documents = case["documents"] or self.documents.build_documents(case)
        missing_required = self.required_unknown_fields(case)
        blocks = []
        ready_docs = [doc for doc in documents if doc["canPrepareBeforeInquiry"]]
        if ready_docs and not has_minju_summary:
            blocks.append({
                "type": "ready_for_documents",
                "title": "지금 준비할 서류",
                "items": [doc["title"] for doc in ready_docs],
            })
        if not has_minju_summary:
            blocks.extend(self.minju_decision_blocks(case))
        info_fields = [field for field in missing_required if field != "exact_address"]
        if info_fields:
            blocks.append({
                "type": "needs_user_info",
                "title": "더 확인할 것",
                "items": [label_for_field(field) for field in info_fields],
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
        required = ["exact_address"]
        return [field for field in required if not slot_known(case, field)]

    @staticmethod
    def minju_decision_blocks(case: dict[str, Any]) -> list[dict[str, Any]]:
        summary = ((case.get("minjuIntake") or {}).get("summary") or {})
        if not summary:
            return []

        blocks: list[dict[str, Any]] = []
        judgement = summary.get("aiJudgement") or {}
        api_plan = summary.get("apiPlan") or {}
        external = summary.get("externalChecks") or {}
        building = external.get("buildingLedger") or {}
        decision = summary.get("decisionEngine") or {}
        provider = (((case.get("minjuIntake") or {}).get("providers") or {}).get("judgement") or "rule")

        status_items = [
            f"건축물대장 API: {building.get('status') or 'not_run'}",
            f"판단 엔진: {decision.get('status') or 'not_run'}",
            f"최종 안내: {judgement.get('decisionStatus') or 'pending'} / {provider}",
        ]
        if api_plan.get("skipReason"):
            status_items.append(str(api_plan["skipReason"]))
        blocks.append({
            "type": "needs_department_check",
            "title": "API/AI 판단 상태",
            "items": status_items[:5],
        })

        questions = []
        for item in judgement.get("questionsToAsk") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "") == "building_use":
                continue
            question = str(item.get("question") or item.get("id") or "").strip()
            if question:
                questions.append(question)
        if questions:
            blocks.append({
                "type": "needs_user_info",
                "title": "추가로 필요한 정보",
                "items": questions[:5],
            })

        final_text = str(judgement.get("summary") or judgement.get("finalResponseDraft") or "").strip()
        if final_text:
            blocks.append({
                "type": "ready_for_documents",
                "title": "AI 안내 요약",
                "items": [line for line in final_text.splitlines() if line.strip()][:3],
            })
        return blocks

    def diagnosis_guidance(self, case: dict[str, Any]) -> dict[str, Any]:
        minju = case.get("minjuIntake") or {}
        summary = minju.get("summary") or {}
        providers = minju.get("providers") or {}
        judgement = summary.get("aiJudgement") or {}
        external = summary.get("externalChecks") or {}
        building = external.get("buildingLedger") or {}
        building_for_display = self.display_building_source(case, building)
        past = external.get("pastBusinessLookup") or {}
        decision = summary.get("decisionEngine") or {}
        api_plan = summary.get("apiPlan") or {}
        missing_info = summary.get("missingInfo") or {}

        provider = str(providers.get("judgement") or "rule")
        decision_status = str(judgement.get("decisionStatus") or "pending")
        summary_text = str(judgement.get("summary") or "").strip()
        final_response = str(judgement.get("finalResponseDraft") or "").strip()
        suitability = self.suitability_status(summary, judgement, building, decision)
        suitability["title"] = self.case_suitability_title(case, suitability["status"])

        api_status_items = [
            f"건축물대장: {self.status_label(building.get('status'))}",
            f"용도/업종 판정: {self.status_label(decision.get('status'))}",
            f"동일 장소 이력: {self.past_business_status_label(past)}",
        ]
        if past.get("allCount", 0):
            api_status_items.append(f"기존 업소 이력 {past.get('allCount')}건 조회")
        if past.get("sameOrSimilarCount", 0):
            api_status_items.append(f"동일/유사 업종 이력 {past.get('sameOrSimilarCount')}건 조회")
        if api_plan.get("skipReason"):
            api_status_items.append(str(api_plan["skipReason"]))

        documents = sorted(case.get("documents") or [], key=lambda item: item.get("priority", 999))
        questions_to_ask = self.question_items(judgement.get("questionsToAsk"), case)[:5]
        for item in self.missing_info_question_items(missing_info, buckets=("recommendedNext",), case=case):
            if item not in questions_to_ask:
                questions_to_ask.append(item)
        for item in self.condition_question_items(case):
            if item not in questions_to_ask:
                questions_to_ask.append(item)
        questions_to_ask = questions_to_ask[:5]
        document_order_items = [] if questions_to_ask else [
            f'{index}. {document["title"]}'
            for index, document in enumerate(documents, start=1)
        ]

        return {
            "title": "건축물대장 확인 결과",
            "headline": self.diagnosis_check_headline(case, building, decision, suitability["status"]),
            "provider": provider,
            "decisionStatus": decision_status,
            "suitability": suitability["status"],
            "suitabilityTitle": suitability["title"],
            "suitabilitySummary": suitability["summary"],
            "summary": summary_text,
            "finalResponseDraft": final_response,
            "apiStatusItems": [],
            "buildingItems": self.building_summary_items(building_for_display),
            "canSayNow": self.string_items(judgement.get("canSayNow"))[:5],
            "cannotConfirmYet": self.string_items(judgement.get("cannotConfirmYet"))[:5],
            "questionsToAsk": questions_to_ask,
            "procedureSteps": [],
            "documentOrderItems": [],
            "departmentItems": [],
        }

    @classmethod
    def suitability_status(
        cls,
        summary: dict[str, Any],
        judgement: dict[str, Any],
        building: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, str]:
        text = " ".join(
            str(value or "")
            for value in [
                judgement.get("summary"),
                judgement.get("finalResponseDraft"),
                decision.get("reason"),
            ]
        )
        blocked_phrases = [
            "진행 불가능",
            "진행 불가",
            "영업 불가능",
            "영업 불가",
            "허가 불가능",
            "허가 불가",
            "신고 불가능",
            "신고 불가",
            "부적합",
            "진행 어려움",
        ]
        if any(phrase in text for phrase in blocked_phrases):
            return {
                "status": "blocked",
                "title": "진행이 어려워 보여요",
                "summary": "건축물/API 확인 결과상 그대로 진행하기 어려운 조건이 있어요.",
            }
        if building.get("status") == "ok" and decision.get("status") == "ok":
            if judgement.get("decisionStatus") == "needs_user_input":
                return {
                    "status": "needs_info",
                    "title": "가능성은 보이지만 추가 정보가 필요해요",
                    "summary": "건축물대장 기준으로는 가능성이 있고, 간판·외부공간·조리 방식 같은 조건을 더 받으면 제출 서류를 확정할 수 있어요.",
                }
            return {
                "status": "available",
                "title": "진행 가능성이 높아요",
                "summary": "건축물대장과 업종 판정 결과를 기준으로 진행 가능성이 높게 나왔어요. 다음으로 세부 운영 조건을 확인해 서류를 확정할게요.",
            }
        if summary.get("apiPlan", {}).get("skipReason"):
            return {
                "status": "pending",
                "title": "API 확인 전이에요",
                "summary": "상세주소나 필수 조건이 부족해 건축물/API 판정은 아직 보류됐어요.",
            }
        return {
            "status": "needs_check",
            "title": "부서 확인이 필요해요",
            "summary": "건축물대장상 가능성은 보이지만 자동 확인만으로 최종 확정은 어려워요. 세부 조건과 담당 부서 확인을 이어갈게요.",
        }

    @staticmethod
    def case_suitability_title(case: dict[str, Any], status: str) -> str:
        activity = str(slot_value(case, "business_activity") or "가게")
        if "카페" in activity or "cafe" in activity.lower() or "휴게음식점" in activity:
            subject = "카페 창업"
        elif "간판" in activity:
            subject = "간판 설치"
        else:
            subject = f"{activity} 준비"

        if status == "blocked":
            return f"{subject}이 어려워 보여요"
        if status in {"available", "needs_info", "needs_check"}:
            return f"{subject} 가능성이 높아요"
        return f"{subject} 판단을 이어갈게요"

    @staticmethod
    def diagnosis_check_headline(
        case: dict[str, Any],
        building: dict[str, Any],
        decision: dict[str, Any],
        status: str,
    ) -> str:
        if status == "blocked":
            return "입력하신 주소의 건축물대장 기준으로 진행이 어려운 조건이 보여요."
        if building.get("status") == "ok" or decision.get("status") == "ok":
            return "입력하신 주소의 건축물대장을 확인했고, 창업 가능성을 먼저 판단했어요."
        if not slot_known(case, "exact_address"):
            return "정확한 주소가 있으면 건축물대장을 조회해 가능성을 판단할 수 있어요."
        return "건축물대장 확인 결과를 바탕으로 추가 확인을 이어갈게요."

    @staticmethod
    def status_label(status: Any) -> str:
        value = str(status or "not_run")
        return {
            "ok": "확인됨",
            "skipped": "보류",
            "missing_index": "데이터 없음",
            "not_run": "미실행",
            "error": "오류",
        }.get(value, value)

    @staticmethod
    def past_business_status_label(past: dict[str, Any]) -> str:
        status = str(past.get("status") or "not_run")
        if status == "ok":
            count = int(past.get("allCount") or past.get("count") or 0)
            if count:
                return f"기존 업소 {count}건 확인"
            return "조회 완료, 기존 이력 없음"
        return {
            "skipped": "보류",
            "missing_index": "LOCALDATA DB 경로 없음",
            "empty_address": "주소 부족",
            "not_run": "미실행",
            "error": "오류",
        }.get(status, status)

    @classmethod
    def condition_question_items(cls, case: dict[str, Any]) -> list[str]:
        fields: list[str] = []
        if not slot_known(case, "liquor_sales"):
            fields.append("liquor_sales")
        if not slot_known(case, "manufacturing_or_simple_sale"):
            fields.append("manufacturing_or_simple_sale")

        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        if not conditions:
            fields.extend(["signboard_planned", "outdoor_space_planned"])
        if "signage_planned" in conditions or slot_value(case, "signboard_planned") is True:
            fields.extend(["signboard_type", "signboard_size", "owner_consent"])
        if "outdoor_space_planned" in conditions or slot_value(case, "outdoor_space_planned") is True:
            fields.extend(["outdoor_location", "outdoor_area", "owner_consent"])

        questions: list[str] = []
        for field in fields:
            if slot_known(case, field):
                continue
            source = next((item for item in QUESTION_BANK if item["field"] == field), None)
            text = str((source or {}).get("question") or label_for_field(field)).strip()
            if text and text not in questions:
                questions.append(text)
        return questions

    @classmethod
    def question_items(cls, items: Any, case: dict[str, Any]) -> list[str]:
        questions: list[str] = []
        for item in items or []:
            if not isinstance(item, dict):
                text = str(item or "").strip()
            else:
                if cls.hide_question_item(case, item):
                    continue
                text = str(item.get("question") or item.get("label") or item.get("id") or "").strip()
            if text:
                questions.append(text)
        return questions

    @classmethod
    def missing_info_question_items(cls, missing_info: dict[str, Any], buckets: tuple[str, ...], case: dict[str, Any]) -> list[str]:
        questions: list[str] = []
        for bucket in buckets:
            for item in missing_info.get(bucket) or []:
                if isinstance(item, dict) and cls.hide_question_item(case, item):
                    continue
                text = ""
                if isinstance(item, dict):
                    text = str(item.get("question") or item.get("label") or item.get("id") or "").strip()
                else:
                    text = str(item or "").strip()
                if text and text not in questions:
                    questions.append(text)
        return questions

    @staticmethod
    def hide_question_item(case: dict[str, Any], item: dict[str, Any]) -> bool:
        question_id = str(item.get("id") or item.get("field") or "").strip()
        if question_id in DISPLAY_QUESTION_SKIP_IDS:
            return True
        if question_id in ADDRESS_QUESTION_IDS and slot_known(case, "exact_address"):
            return True
        if question_id in FLOOR_QUESTION_IDS:
            address = str(slot_value(case, "exact_address") or "")
            if slot_known(case, "floor_unit") or any(token in address for token in ["층", "호"]):
                return True
        known_by_id = {
            "area": "area",
            "area_if_known": "area",
            "liquor_sales": "liquor_sales",
            "business_concept": "business_activity",
            "signboard": "signboard_planned",
            "outdoor_space": "outdoor_space_planned",
            "signboard_type": "signboard_type",
            "signboard_size": "signboard_size",
            "owner_consent": "owner_consent",
            "outdoor_location": "outdoor_location",
            "outdoor_area": "outdoor_area",
        }
        field = known_by_id.get(question_id)
        return bool(field and slot_known(case, field))

    @staticmethod
    def string_items(items: Any) -> list[str]:
        values: list[str] = []
        for item in items or []:
            if isinstance(item, dict):
                text = str(
                    item.get("label")
                    or item.get("title")
                    or item.get("name")
                    or item.get("question")
                    or item.get("id")
                    or ""
                ).strip()
                status = str(item.get("status") or "").strip()
                if status and text:
                    text = f"{text}: {status}"
            else:
                text = str(item or "").strip()
            if text:
                values.append(text)
        return values

    @staticmethod
    def display_building_source(case: dict[str, Any], building: dict[str, Any]) -> dict[str, Any]:
        client_building = case.get("clientBuildingLedger") if isinstance(case.get("clientBuildingLedger"), dict) else {}
        building_summary = building.get("summary") if isinstance(building.get("summary"), dict) else {}
        client_summary = client_building.get("summary") if isinstance(client_building.get("summary"), dict) else {}
        if not building_summary and client_summary:
            return client_building
        if building_summary and client_summary:
            merged = dict(client_building)
            merged.update(building)
            merged["summary"] = {**client_summary, **building_summary}
            return merged
        return building

    @staticmethod
    def building_summary_items(building_or_summary: dict[str, Any]) -> list[str]:
        if not building_or_summary:
            return []

        summary = (
            building_or_summary.get("summary")
            if isinstance(building_or_summary.get("summary"), dict)
            else building_or_summary
        )
        items: list[str] = []
        for label, key in [
            ("주용도", "mainPurpsCdNm"),
            ("기타용도", "etcPurps"),
            ("위반건축물 여부", "violated"),
            ("대장상 면적", "areaM2"),
        ]:
            value = summary.get(key)
            if value not in (None, "", []):
                items.append(f"{label}: {ViewBuilder.format_building_value(key, value)}")

        floor_uses = summary.get("floorUses") or summary.get("usesByFloor") or []
        floor_texts = []
        for floor in floor_uses if isinstance(floor_uses, list) else []:
            if isinstance(floor, dict):
                bits = [
                    str(floor.get("floor") or floor.get("flrNoNm") or "").strip(),
                    str(floor.get("mainPurpsCdNm") or floor.get("mainPurps") or "").strip(),
                    str(floor.get("etcPurps") or "").strip(),
                ]
                text = " ".join(bit for bit in bits if bit)
            else:
                text = str(floor or "").strip()
            if text:
                floor_texts.append(text)
        if floor_texts:
            items.append("층별 용도: " + " / ".join(floor_texts[:4]))

        land_zones = summary.get("landUseZones") or summary.get("landZones") or summary.get("zones") or []
        if isinstance(land_zones, list) and land_zones:
            items.append("지역지구: " + ", ".join(str(zone) for zone in land_zones[:4]))
        return items

    @staticmethod
    def format_building_value(key: str, value: Any) -> str:
        if key == "violated":
            raw = str(value).strip().lower()
            if raw in {"false", "n", "no", "0", "해당없음", "없음"}:
                return "해당 없음"
            if raw in {"true", "y", "yes", "1", "위반", "있음"}:
                return "위반 있음"
        if key == "areaM2":
            text = str(value).strip()
            return text if "㎡" in text else f"{text}㎡"
        return str(value)

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
        return updates

    def dashboard_primary_label(self, case: dict[str, Any]) -> str:
        if any(doc["status"] != "completed" for doc in case["documents"]):
            return "서류 이어가기"
        return "제출 현황 보기"

    @staticmethod
    def progress_stage(machine_state: str) -> str:
        if machine_state in {"NEEDS_INFO", "UNDERSTAND", "INTAKE"}:
            return "intake"
        if machine_state in {"DIAGNOSIS", "CONFIRM_UNDERSTANDING"}:
            return "diagnosis"
        if machine_state == "DOCUMENTS":
            return "documents"
        if machine_state in {"INQUIRY", "ANSWER_REVIEW"}:
            return "dashboard"
        if machine_state == "SUBMITTED":
            return "submitted"
        return "dashboard"


view_builder = ViewBuilder()
