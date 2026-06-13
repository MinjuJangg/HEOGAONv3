from __future__ import annotations

import re
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
    "building_use",
}

DETAIL_FOLLOWUP_FIELDS = {
    "signboard_planned",
    "signboard_type",
    "signboard_size",
    "signboard_location",
    "signboard_image",
    "owner_consent",
    "outdoor_space_planned",
    "outdoor_location",
    "outdoor_area",
}

ADDRESS_QUESTION_IDS = {
    "address",
    "base_address",
    "detailed_address",
    "detailed_address_for_building_check",
}

FLOOR_QUESTION_IDS = {"floor_unit", "floor_or_unit_if_known"}
FLOOR_OR_UNIT_HINT_RE = re.compile(r"(?:지하\s*)?\d+\s*층|[A-Za-z]?\d{1,5}\s*호")
FLOOR_FOLLOWUP_TEXT_RE = re.compile(r"몇\s*층|실제로\s*몇\s*층|층수|층\s*/\s*호수|층과\s*호수|호수|호실")


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
        field = current.get("field")
        is_detail_followup = bool(field in DETAIL_FOLLOWUP_FIELDS and ViewBuilder.detailed_floor_unit_known(case))
        show_detail_intro = is_detail_followup and bool(case.get("detailFollowupIntroPending"))
        return {
            "type": "slot_question",
            "field": field,
            "title": "추가 확인할 정보가 있어요!" if show_detail_intro else current.get("question") or "확인이 더 필요해요",
            "subtitle": "간판·외부공간 조건에 따라 필요한 서류가 달라질 수 있어요." if show_detail_intro else current.get("why") or "",
            "prompt": (current.get("question") or "") if show_detail_intro else "",
            "promptDescription": (current.get("why") or "") if show_detail_intro else "",
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
        documents = case["documents"]
        return {
            "type": "documents",
            "title": "필요 서류를 준비해요",
            "documents": documents,
            "completedDocumentIds": case["completedDocumentIds"],
            "durationEstimate": self.duration_estimate(documents),
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
            "suitabilityTitle": "",
            "suitabilitySummary": "",
            "nextButtonLabel": "맞아요, 계속",
            "editButtonLabel": "아니에요, 수정할게요",
        }

    @classmethod
    def understanding_items(cls, case: dict[str, Any]) -> list[dict[str, str]]:
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
                "value": cls.display_understanding_value(case, field, value),
            })
        return items

    @classmethod
    def display_understanding_value(cls, case: dict[str, Any], field: str, value: Any) -> str:
        if field == "business_activity":
            return cls.display_business_activity(case, value)
        if field == "exact_address":
            return cls.display_exact_address(case, value)
        return display_value_for_field(field, value)

    @staticmethod
    def display_exact_address(case: dict[str, Any], value: Any) -> str:
        address = str(value or "").strip()
        detail = str(slot_value(case, "floor_unit") or "").strip()
        if not address or not detail:
            return address

        cleaned = address
        for token in FLOOR_OR_UNIT_HINT_RE.findall(detail):
            cleaned = re.sub(rf"\s*{re.escape(token)}\s*$", "", cleaned).strip()
            cleaned = re.sub(rf"\s*{re.escape(token)}(?=\s|,|$)", " ", cleaned).strip()
        return re.sub(r"\s{2,}", " ", cleaned).strip(" ,") or address

    @classmethod
    def display_business_activity(cls, case: dict[str, Any], value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""

        ai_display = cls.ai_business_type_display(case)
        if ai_display:
            return ai_display

        if "(" in raw and ")" in raw and any(term in raw for term in ("음식점", "제과점")):
            return raw

        context = " ".join(
            str(item or "")
            for item in [
                raw,
                case.get("rawInput"),
                slot_value(case, "business_activity"),
                slot_value(case, "manufacturing_or_simple_sale"),
            ]
        )
        compact = re.sub(r"\s+", "", context).lower()
        raw_compact = re.sub(r"\s+", "", raw).lower()
        liquor_sales = slot_value(case, "liquor_sales") is True

        if "bakery" in compact or "제과" in compact or "베이커" in compact or "빵" in compact:
            label = "제과/디저트"
            business_type = "제과점영업"
        elif "cafe" in compact or "coffee" in compact or "카페" in compact or "커피" in compact or "휴게음식점" in compact:
            label = "카페·주류 판매" if liquor_sales else ("카페" if any(term in compact for term in ("cafe", "coffee", "카페", "커피")) else "휴게음식점")
            business_type = "일반음식점영업" if liquor_sales else "휴게음식점영업"
        elif "restaurant" in compact or "일반음식점" in compact or "식당" in compact or "음식점" in compact:
            label = "음식점"
            business_type = "일반음식점영업"
        else:
            label = cls.localize_business_label(raw)
            business_type = cls.infer_business_type_label(case, raw)

        if business_type and business_type not in label:
            return f"{label}({business_type})"
        return label

    @staticmethod
    def ai_business_type_display(case: dict[str, Any]) -> str:
        for key in ("minjuIntake", "minjuDraft"):
            judgement = ((((case.get(key) or {}).get("summary") or {}).get("aiJudgement") or {}).get("businessTypeJudgement") or {})
            if not isinstance(judgement, dict):
                continue
            label = str(judgement.get("displayLabel") or "").strip()
            business_type = str(judgement.get("businessType") or "").strip()
            if not label or not business_type or business_type == "확인 필요":
                continue
            if business_type in label:
                return label
            return f"{label}({business_type})"
        return ""

    @staticmethod
    def localize_business_label(value: str) -> str:
        normalized = re.sub(r"\s+", "", value).lower()
        return {
            "cafe": "카페",
            "coffee": "카페",
            "coffeeshop": "카페",
            "restaurant": "음식점",
            "bakery": "제과/디저트",
        }.get(normalized, value)

    @staticmethod
    def infer_business_type_label(case: dict[str, Any], value: str) -> str:
        text = " ".join(
            str(item or "")
            for item in [
                value,
                case.get("rawInput"),
                slot_value(case, "business_activity"),
            ]
        )
        if "일반음식점" in text:
            return "일반음식점영업"
        if "휴게음식점" in text:
            return "휴게음식점영업"
        if "제과점" in text:
            return "제과점영업"
        return ""

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
        suitability = self.suitability_status(case, summary, judgement, building, decision)
        has_floor_detail = self.detailed_floor_unit_known(case)
        is_floor_detail_result = has_floor_detail and bool(case.get("floorDetailResultPending"))
        suitability["title"] = self.case_suitability_title(case, suitability["status"])
        if is_floor_detail_result and suitability["status"] != "blocked":
            suitability["title"] = "층별 용도를 확인했어요"
            suitability["summary"] = "입력한 층/호수 기준으로 층별 용도를 다시 확인했어요. 이제 간판·외부공간 같은 추가 정보만 더 확인하면 서류를 확정할 수 있어요."

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
        questions_to_ask = self.dedupe_question_texts([
            *self.question_items(judgement.get("questionsToAsk"), case),
            *self.missing_info_question_items(missing_info, buckets=("recommendedNext",), case=case),
            *self.condition_question_items(case),
        ])[:5]
        document_order_items = [] if questions_to_ask else [
            f'{index}. {document["title"]}'
            for index, document in enumerate(documents, start=1)
        ]

        return {
            "title": "세부 층·호수 확인 결과 가능해요" if is_floor_detail_result else "건축물대장 확인 결과",
            "headline": (
                "입력하신 층/호수를 반영해 건축물대장을 다시 확인했어요."
                if is_floor_detail_result
                else self.diagnosis_check_headline(case, building, decision, suitability["status"])
            ),
            "provider": provider,
            "decisionStatus": decision_status,
            "suitability": suitability["status"],
            "suitabilityTitle": suitability["title"],
            "suitabilitySummary": suitability["summary"],
            "summary": summary_text,
            "finalResponseDraft": final_response,
            "apiStatusItems": [],
            "buildingItems": self.building_summary_items(building_for_display, case=case),
            "hideBuildingSummary": False,
            "canSayNow": self.string_items(judgement.get("canSayNow"))[:5],
            "cannotConfirmYet": self.string_items(judgement.get("cannotConfirmYet"))[:5],
            "questionsToAsk": questions_to_ask,
            "questionsTitle": "추가 확인할 정보가 있어요!" if is_floor_detail_result else "추가로 확인할 것",
            "hideQuestionsSummary": is_floor_detail_result,
            "procedureSteps": [],
            "documentOrderItems": [],
            "departmentItems": [],
        }

    @classmethod
    def suitability_status(
        cls,
        case: dict[str, Any],
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
                signal_text = document_service.condition_signal_text(case)
                condition_labels = ["간판", "조리 방식"]
                outdoor_known_no = slot_value(case, "outdoor_space_planned") is False or document_service.has_negative_outdoor_signal(signal_text)
                if not outdoor_known_no:
                    condition_labels.insert(1, "외부공간")
                return {
                    "status": "needs_info",
                    "title": "가능성은 보이지만 추가 정보가 필요해요",
                    "summary": f"건축물대장 기준으로는 가능성이 있고, {'·'.join(condition_labels)} 같은 조건을 더 받으면 제출 서류를 확정할 수 있어요.",
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

    @classmethod
    def duration_estimate(cls, documents: list[dict[str, Any]]) -> dict[str, Any] | None:
        durations: list[dict[str, Any]] = []
        for document in documents:
            bounds = cls.document_duration_bounds(document)
            if not bounds:
                continue
            min_days, max_days = bounds
            if max_days <= 0:
                continue
            durations.append({
                "title": str(document.get("title") or ""),
                "display": str(document.get("perceivedDuration") or ""),
                "phase": cls.duration_phase(document),
                "minDays": min_days,
                "maxDays": max_days,
            })

        if not durations:
            return None

        phase_totals: dict[str, tuple[int, int]] = {
            "pre": (0, 0),
            "submission": (0, 0),
            "after": (0, 0),
        }
        for item in durations:
            phase = str(item["phase"])
            current_min, current_max = phase_totals.get(phase, (0, 0))
            phase_totals[phase] = (
                max(current_min, int(item["minDays"])),
                max(current_max, int(item["maxDays"])),
            )

        min_days = sum(value[0] for value in phase_totals.values())
        max_days = sum(value[1] for value in phase_totals.values())
        basis_items = [
            f'{item["title"]}: {item["display"] or cls.format_business_day_range(item["minDays"], item["maxDays"])}'
            for item in sorted(durations, key=lambda value: (value["maxDays"], value["minDays"]), reverse=True)[:3]
        ]
        return {
            "title": "예상 전체 소요 기간",
            "rangeLabel": cls.format_business_day_range(min_days, max_days),
            "summary": "동시 준비 가능한 서류는 병렬로 진행한다고 보고 계산했어요.",
            "minBusinessDays": min_days,
            "maxBusinessDays": max_days,
            "basisItems": basis_items,
            "note": "보건소·구청 처리 상황과 보완 요청 여부에 따라 달라질 수 있어요.",
        }

    @staticmethod
    def document_duration_bounds(document: dict[str, Any]) -> tuple[int, int] | None:
        processing_time = document.get("processingTime") if isinstance(document.get("processingTime"), dict) else {}
        if processing_time:
            min_days = ViewBuilder.int_value(processing_time.get("minBusinessDays"))
            max_days = ViewBuilder.int_value(processing_time.get("maxBusinessDays"))
            min_minutes = ViewBuilder.int_value(processing_time.get("minMinutes"))
            max_minutes = ViewBuilder.int_value(processing_time.get("maxMinutes"))
            if min_days or max_days or min_minutes or max_minutes:
                return (
                    min_days + ViewBuilder.minutes_to_business_days(min_minutes),
                    max_days + ViewBuilder.minutes_to_business_days(max_minutes),
                )

        text = str(document.get("perceivedDuration") or "")
        if not text or "확인 필요" in text or "공공 처리기간 없음" in text:
            return None
        day_numbers = [int(value) for value in re.findall(r"(\d+)\s*일", text)]
        if day_numbers:
            return min(day_numbers), max(day_numbers)
        if re.search(r"즉시|당일|시간", text):
            return (0, 0)
        return None

    @staticmethod
    def duration_phase(document: dict[str, Any]) -> str:
        blocker = str(document.get("scheduleBlockerType") or "")
        title = str(document.get("title") or "")
        if blocker == "after_food_report" or "사업자등록" in title:
            return "after"
        if blocker == "submission_after_prerequisites" or "영업신고" in title:
            return "submission"
        return "pre"

    @staticmethod
    def minutes_to_business_days(minutes: int) -> int:
        if minutes <= 0:
            return 0
        return 1 if minutes > 240 else 0

    @staticmethod
    def int_value(value: Any) -> int:
        try:
            return max(0, int(str(value or "").strip()))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def format_business_day_range(min_days: int, max_days: int) -> str:
        if min_days <= 0 and max_days <= 0:
            return "당일"
        if min_days <= 0:
            return f"당일~최대 {max_days}영업일"
        if min_days == max_days:
            return f"약 {min_days}영업일"
        return f"최소 {min_days}영업일 ~ 최대 {max_days}영업일"

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
        signal_text = document_service.condition_signal_text(case)
        has_signage = document_service.has_signage_signal(case)
        has_outdoor = document_service.has_outdoor_signal(case)
        signage_known_no = slot_value(case, "signboard_planned") is False or document_service.has_negative_signage_signal(signal_text)
        outdoor_known_no = slot_value(case, "outdoor_space_planned") is False or document_service.has_negative_outdoor_signal(signal_text)
        if not conditions:
            if not has_signage and not signage_known_no:
                fields.append("signboard_planned")
            if not has_outdoor and not outdoor_known_no:
                fields.append("outdoor_space_planned")
        if not signage_known_no and (has_signage or "signage_planned" in conditions or slot_value(case, "signboard_planned") is True):
            fields.extend(["signboard_type", "signboard_size", "owner_consent", "signboard_image"])
        if not outdoor_known_no and (has_outdoor or "outdoor_space_planned" in conditions or slot_value(case, "outdoor_space_planned") is True):
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
            if cls.hide_question_text(case, text):
                continue
            if text:
                questions.append(text)
        return questions

    @classmethod
    def dedupe_question_texts(cls, items: list[str]) -> list[str]:
        questions: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = re.sub(r"\s+", " ", str(item or "")).strip()
            if not text:
                continue
            key = cls.question_semantic_key(text)
            if key in seen:
                continue
            seen.add(key)
            questions.append(text)
        return questions

    @staticmethod
    def question_semantic_key(text: str) -> str:
        compact = re.sub(r"[\s\W_]+", "", text or "").lower()
        if not compact:
            return ""
        if any(token in compact for token in ("건물주", "관리인", "소유자", "대지소유자")) and any(token in compact for token in ("승낙", "동의", "허락", "사용권")):
            return "owner_consent"
        if "간판" in compact:
            if any(token in compact for token in ("크기", "면적", "가로", "세로", "높이", "길이", "규격")):
                return "signboard_size"
            if "종류" in compact or ("어떤" in compact and any(token in compact for token in ("설치", "변경"))):
                return "signboard_type"
            if any(token in compact for token in ("위치", "어디")):
                return "signboard_location"
            if any(token in compact for token in ("설치", "변경", "바꿀", "예정", "계획")):
                return "signboard_planned"
        if any(token in compact for token in ("외부", "테이블", "테라스", "보도", "도로")):
            if any(token in compact for token in ("면적", "크기", "수량", "몇개", "몇대")):
                return "outdoor_area"
            if any(token in compact for token in ("위치", "어디", "사유지", "도로", "보도")):
                return "outdoor_location"
            if any(token in compact for token in ("사용", "예정", "계획", "둘", "두", "좌석")):
                return "outdoor_space_planned"
        if any(token in compact for token in ("술", "주류")):
            return "liquor_sales"
        if any(token in compact for token in ("직접", "조리", "제조", "가공", "완제품")):
            return "manufacturing_or_simple_sale"
        return compact

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
                if cls.hide_question_text(case, text):
                    continue
                if text and text not in questions:
                    questions.append(text)
        return questions

    @classmethod
    def hide_question_item(cls, case: dict[str, Any], item: dict[str, Any]) -> bool:
        question_id = str(item.get("id") or item.get("field") or "").strip()
        if question_id in DISPLAY_QUESTION_SKIP_IDS:
            return True
        if question_id in ADDRESS_QUESTION_IDS and slot_known(case, "exact_address"):
            return True
        if question_id in FLOOR_QUESTION_IDS:
            if cls.has_floor_or_unit_hint(case):
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
            "signboard_image": "signboard_image",
            "owner_consent": "owner_consent",
            "outdoor_location": "outdoor_location",
            "outdoor_area": "outdoor_area",
        }
        field = known_by_id.get(question_id)
        return bool(field and slot_known(case, field))

    @classmethod
    def hide_question_text(cls, case: dict[str, Any], text: str) -> bool:
        if not text or not FLOOR_FOLLOWUP_TEXT_RE.search(text):
            return False
        return cls.has_floor_or_unit_hint(case) or bool(FLOOR_OR_UNIT_HINT_RE.search(text))

    @staticmethod
    def has_floor_or_unit_hint(case: dict[str, Any]) -> bool:
        if slot_known(case, "floor_unit"):
            return True

        candidates: list[str] = [
            str(slot_value(case, "exact_address") or ""),
            str(slot_value(case, "location") or ""),
            str(case.get("rawInput") or ""),
        ]
        for answer in case.get("answers") or []:
            if isinstance(answer, dict):
                candidates.extend(str(answer.get(key) or "") for key in ("answer", "text", "value"))
            else:
                candidates.append(str(answer or ""))

        return any(FLOOR_OR_UNIT_HINT_RE.search(text) for text in candidates if text)

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
    def building_summary_items(building_or_summary: dict[str, Any], case: dict[str, Any] | None = None) -> list[str]:
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
        target_floor = ViewBuilder.target_floor_number(case or {})
        for floor in floor_uses if isinstance(floor_uses, list) else []:
            if isinstance(floor, dict):
                floor_label = str(floor.get("floor") or floor.get("flrNoNm") or "").strip()
                use_bits = ViewBuilder.compact_building_use_bits([
                    str(floor.get("mainPurpsCdNm") or floor.get("mainPurps") or "").strip(),
                    str(floor.get("etcPurps") or "").strip(),
                ])
                text = " ".join(bit for bit in [floor_label, *use_bits] if bit)
            else:
                text = ViewBuilder.clean_floor_use_text(str(floor or ""))
            if text:
                floor_texts.append(text)
        if target_floor is not None:
            targeted = [
                text
                for text in floor_texts
                if ViewBuilder.floor_use_matches_target(text, target_floor)
            ]
            if targeted:
                floor_texts = targeted
        if floor_texts:
            floor_texts = ViewBuilder.group_floor_use_texts(floor_texts)
            items.append("층별 용도: " + " / ".join(floor_texts[:4]))

        land_zones = summary.get("landUseZones") or summary.get("landZones") or summary.get("zones") or []
        if isinstance(land_zones, list) and land_zones:
            items.append("지역지구: " + ", ".join(str(zone) for zone in land_zones[:4]))
        return items

    @staticmethod
    def compact_building_use_bits(values: list[str]) -> list[str]:
        unique: list[str] = []
        for value in values:
            text = re.sub(r"\s+", " ", value or "").strip()
            key = re.sub(r"[\s\W_]+", "", text).lower()
            if not text or not key:
                continue
            replaced = False
            should_skip = False
            for index, existing in enumerate(unique):
                existing_key = re.sub(r"[\s\W_]+", "", existing).lower()
                if key == existing_key:
                    should_skip = True
                    break
                if key in existing_key:
                    should_skip = True
                    break
                if existing_key in key:
                    unique[index] = text
                    replaced = True
                    break
            if should_skip:
                continue
            if replaced:
                continue
            unique.append(text)
        return unique

    @staticmethod
    def clean_floor_use_text(value: str) -> str:
        text = re.sub(r"\s+", " ", value or "").strip()
        if not text:
            return ""
        match = re.match(r"^((?:지하\s*)?\d+\s*층|지\s*\d+\s*층|[bB]\d+\s*층?|옥탑)\s+(.+)$", text)
        if not match:
            return text
        floor_label = re.sub(r"\s+", "", match.group(1))
        uses = ViewBuilder.compact_building_use_bits(match.group(2).split())
        return " ".join([floor_label, *uses]).strip()

    @staticmethod
    def group_floor_use_texts(values: list[str]) -> list[str]:
        grouped: list[dict[str, Any]] = []
        passthrough: list[str] = []
        for value in values:
            parsed = ViewBuilder.parse_floor_use_text(value)
            if not parsed:
                if value not in passthrough:
                    passthrough.append(value)
                continue
            floor_label, use_text = parsed
            use_key = re.sub(r"[\s\W_]+", "", use_text).lower()
            target = next((item for item in grouped if item["key"] == use_key), None)
            if target:
                if floor_label not in target["floors"]:
                    target["floors"].append(floor_label)
            else:
                grouped.append({"key": use_key, "floors": [floor_label], "use": use_text})
        return [f"{'·'.join(item['floors'])} {item['use']}" for item in grouped] + passthrough

    @staticmethod
    def parse_floor_use_text(value: str) -> tuple[str, str] | None:
        text = re.sub(r"\s+", " ", value or "").strip()
        match = re.match(r"^((?:지하\s*)?\d+\s*층|지\s*\d+\s*층|[bB]\d+\s*층?|옥탑)\s+(.+)$", text)
        if not match:
            return None
        return re.sub(r"\s+", "", match.group(1)), match.group(2).strip()

    @staticmethod
    def detailed_floor_unit_known(case: dict[str, Any]) -> bool:
        return slot_known(case, "floor_unit") or ViewBuilder.target_floor_number(case) is not None

    @staticmethod
    def target_floor_number(case: dict[str, Any]) -> int | None:
        candidates = [
            str(slot_value(case, "floor_unit") or ""),
            str(slot_value(case, "exact_address") or ""),
            str(case.get("rawInput") or ""),
        ]
        for text in candidates:
            floor = ViewBuilder.floor_number_from_text(text)
            if floor is not None:
                return floor
        return None

    @staticmethod
    def floor_number_from_text(text: str) -> int | None:
        value = re.sub(r"\s+", " ", text or "").strip()
        if not value:
            return None
        basement = re.search(r"(?:지하|B)\s*(\d+)\s*층?", value, re.IGNORECASE)
        if basement:
            return -int(basement.group(1))
        floor = re.search(r"(?<!지하\s)(?<!B)(\d+)\s*층", value, re.IGNORECASE)
        if floor:
            return int(floor.group(1))
        unit = re.search(r"(\d{3,5})\s*호", value)
        if unit:
            number = unit.group(1)
            return int(number[:-2])
        return None

    @staticmethod
    def floor_use_matches_target(value: str, target_floor: int) -> bool:
        parsed = ViewBuilder.parse_floor_use_text(value)
        if not parsed:
            return False
        label, _ = parsed
        normalized = re.sub(r"\s+", "", label).lower()
        if target_floor < 0:
            floor = abs(target_floor)
            return normalized in {f"지{floor}층", f"지하{floor}층", f"b{floor}", f"b{floor}층"}
        return normalized == f"{target_floor}층"

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
