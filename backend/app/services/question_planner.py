from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.data.catalog import FIELD_VALUE_MAP, MAX_TOTAL_QUESTIONS, QUESTION_BANK, unknown_option
from app.services.document_service import DocumentService, document_service
from app.services.graph_rag_service import GraphRagService, graph_rag_service
from app.services.slot_utils import (
    admin_term_for,
    append_condition,
    append_unique,
    as_list,
    now_iso,
    set_slot,
    slot_value,
)


SYSTEM_DERIVED_FIELDS = {"building_use", "area"}
SIGNAGE_ONLY_ALLOWED_FIELDS = {
    "business_activity",
    "exact_address",
    "floor_unit",
    "condition_screening",
    "signboard_planned",
    "signboard_type",
    "signboard_size",
    "signboard_location",
    "signboard_image",
    "owner_consent",
}
TRANSFER_SKIP_FIELDS = {"hygieneTraining", "healthCertificate", "fireCertificate"}

MINJU_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "address": ("exact_address",),
    "base_address": ("exact_address",),
    "detailed_address": ("exact_address",),
    "detailed_address_for_building_check": ("exact_address",),
    "floor_unit": ("floor_unit",),
    "floor_or_unit_if_known": ("floor_unit",),
    "area": ("area",),
    "area_if_known": ("area",),
    "business_concept": ("business_activity",),
    "business_type": ("business_activity",),
    "business_type_if_known": ("business_activity",),
    "current_business_type": ("business_activity",),
    "target_business_type": ("business_activity",),
    "target_permit_or_business_type": ("business_activity",),
    "sales_items": ("business_activity",),
    "service_goal": ("business_activity",),
    "liquor_sales": ("liquor_sales",),
    "liquor_sales_if_relevant": ("liquor_sales",),
    "signboard": ("signboard_planned",),
    "signboard_type": ("signboard_type",),
    "signboard_size": ("signboard_size",),
    "signboard_location": ("signboard_location",),
    "signboard_image": ("signboard_image",),
    "owner_consent": ("owner_consent",),
    "owner_or_manager_permission": ("owner_consent",),
    "manager_consent": ("owner_consent",),
    "outdoor_space": ("outdoor_space_planned",),
    "outdoor_location": ("outdoor_location",),
    "outdoor_area": ("outdoor_area",),
    "lpg_use": ("condition_screening",),
    "lpg_facility": ("condition_screening",),
    "gas_use": ("condition_screening",),
    "lease_contract": ("lease_contract",),
    "takeover_or_existing_business": ("takeover_type",),
    "takeover_type": ("takeover_type",),
    "hygieneTraining": ("hygieneTraining",),
    "hygiene_training": ("hygieneTraining",),
    "healthCertificate": ("healthCertificate",),
    "health_certificate": ("healthCertificate",),
    "fireCertificate": ("fireCertificate",),
    "fire_certificate": ("fireCertificate",),
}


class QuestionPlanner:
    def __init__(
        self,
        documents: DocumentService = document_service,
        graph_rag: GraphRagService = graph_rag_service,
    ) -> None:
        self.documents = documents
        self.graph_rag = graph_rag

    def build_question_plan(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        minju_questions = self.build_minju_question_plan(case, buckets=("requiredNow",))
        if minju_questions:
            return minju_questions

        graph_rag_questions = self.graph_rag.build_question_plan(case)
        if graph_rag_questions:
            return self.filter_question_plan(case, graph_rag_questions)

        case.setdefault("ai", {})["questionSource"] = "catalog"
        return self.filter_question_plan(case, QUESTION_BANK)

    def build_minju_question_plan(
        self,
        case: dict[str, Any],
        buckets: tuple[str, ...] = ("requiredNow", "recommendedNext"),
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        fields = self.minju_missing_fields(case, buckets=buckets)
        questions = self.questions_for_fields(fields)
        filtered = self.filter_question_plan(case, questions)
        if filtered:
            case.setdefault("ai", {})["questionSource"] = "minju_missing_info"
        return filtered[: limit or MAX_TOTAL_QUESTIONS]

    def minju_missing_fields(self, case: dict[str, Any], buckets: tuple[str, ...]) -> list[str]:
        missing = self.minju_summary(case).get("missingInfo") or {}
        fields: list[str] = []
        for bucket in buckets:
            for item in missing.get(bucket) or []:
                for field in self.fields_for_minju_item(case, item):
                    append_unique(fields, field)
        return fields

    @classmethod
    def fields_for_minju_item(cls, case: dict[str, Any], item: Any) -> list[str]:
        if isinstance(item, dict):
            raw_id = str(item.get("id") or item.get("field") or "").strip()
        else:
            raw_id = str(item or "").strip()
        if not raw_id:
            return []

        field_ids = list(MINJU_FIELD_ALIASES.get(raw_id, (raw_id,)))
        if raw_id in {"address", "base_address", "detailed_address", "detailed_address_for_building_check"}:
            if slot_value(case, "exact_address") and not cls.floor_unit_known(case):
                field_ids = ["floor_unit"]
        return field_ids

    @staticmethod
    def questions_for_fields(fields: list[str]) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        for field in fields:
            source = next((item for item in QUESTION_BANK if item["field"] == field), None)
            if source and not any(item["field"] == field for item in questions):
                questions.append(deepcopy(source))
        return questions

    @staticmethod
    def minju_summary(case: dict[str, Any]) -> dict[str, Any]:
        draft = ((case.get("minjuDraft") or {}).get("summary") or {})
        if draft:
            return draft
        return ((case.get("minjuIntake") or {}).get("summary") or {})

    @staticmethod
    def filter_question_plan(case: dict[str, Any], questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pending = []
        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        answered = set(case.get("questionLoop", {}).get("answeredFields") or [])
        text = f"{case.get('rawInput') or ''} {slot_value(case, 'business_activity') or ''}"
        user_answered_conditions = "condition_screening" in answered
        has_signage = document_service.has_affirmative_signage(
            case,
            text,
            conditions,
            user_answered_conditions,
            "signboard_planned" in answered,
        )
        has_outdoor = document_service.has_affirmative_outdoor(
            case,
            text,
            conditions,
            user_answered_conditions,
            "outdoor_space_planned" in answered,
        )
        signage_detail_fields = {"signboard_type", "signboard_size", "signboard_location", "signboard_image"}
        outdoor_detail_fields = {"outdoor_location", "outdoor_area"}
        for question in questions:
            field = question["field"]
            if field in SYSTEM_DERIVED_FIELDS:
                continue
            if document_service.is_signage_only_case(case) and field not in SIGNAGE_ONLY_ALLOWED_FIELDS:
                continue
            if document_service.is_transfer_case(case) and field in TRANSFER_SKIP_FIELDS:
                continue
            if field in signage_detail_fields and not has_signage:
                continue
            if field in outdoor_detail_fields and not has_outdoor:
                continue
            if field == "owner_consent" and not (has_signage or has_outdoor):
                continue
            if field == "exact_address" and slot_value(case, "exact_address"):
                continue
            if field == "floor_unit" and QuestionPlanner.floor_unit_known(case):
                continue
            if field == "signboard_planned" and "signage_planned" in as_list(slot_value(case, "condition_screening")):
                continue
            if field == "outdoor_space_planned" and "outdoor_space_planned" in as_list(slot_value(case, "condition_screening")):
                continue
            if field == "condition_screening" and "condition_screening" in case["slots"]:
                continue
            if field in case["slots"]:
                continue
            normalized = deepcopy(question)
            if normalized.get("inputMode") in {"single_select", "multi_select"}:
                options = normalized.setdefault("options", [])
                if not any(option.get("id") == "unknown" for option in options):
                    options.append(unknown_option())
            pending.append(normalized)
        return pending[:MAX_TOTAL_QUESTIONS]

    @staticmethod
    def floor_unit_known(case: dict[str, Any]) -> bool:
        if slot_value(case, "floor_unit"):
            return True
        address = str(slot_value(case, "exact_address") or "")
        return bool(re.search(r"(?:지하\s*)?\d+\s*층|[A-Za-z]?\d{1,5}\s*호", address))

    def start_or_finish_question_loop(self, case: dict[str, Any]) -> dict[str, Any]:
        loop = case["questionLoop"]
        next_question = self.next_loop_question(loop)
        if next_question:
            loop["status"] = "active"
            loop["current"] = next_question
            self.record_question_ask(loop, next_question["field"])
            case["machineState"] = "NEEDS_INFO"
            return case

        self.finish_question_loop(case, "completed_or_limited")
        return case

    def next_loop_question(self, loop: dict[str, Any]) -> dict[str, Any] | None:
        if loop["totalAsked"] >= loop["maxTotalQuestions"]:
            loop["stopReason"] = "max_total_questions"
            return None

        answered = set(loop["answeredFields"])
        unknown = set(loop["unknownFields"])
        skipped = set(loop["skippedFields"])
        attempts = loop["attempts"]

        for question in loop["pendingQuestions"]:
            field = question["field"]
            if field in answered or field in unknown or field in skipped:
                continue
            if attempts.get(field, 0) >= loop["maxAttemptsPerField"]:
                append_unique(loop["unknownFields"], field)
                continue
            return question
        return None

    @staticmethod
    def record_question_ask(loop: dict[str, Any], field: str) -> None:
        loop["attempts"][field] = loop["attempts"].get(field, 0) + 1
        append_unique(loop["askedFields"], field)
        loop["totalAsked"] += 1

    def finish_question_loop(self, case: dict[str, Any], reason: str) -> None:
        case["questionLoop"]["status"] = "complete"
        case["questionLoop"]["current"] = None
        case["questionLoop"]["stopReason"] = reason
        case["machineState"] = "DIAGNOSIS"
        # 최초 진단 때만 생성한다. 후속 질문으로 재진입할 때 다시 만들면 이미 완료한
        # 서류 진행 상태가 초기화되어 완료(SUBMITTED) 화면에 영영 도달하지 못한다.
        if not case.get("documents"):
            case["documents"] = self.documents.build_documents(case)
        case["inquiryTasks"] = []

    def followup_fields(self, case: dict[str, Any], fields: list[str]) -> list[str]:
        """후속 질문으로 실제로 물을 수 있는 슬롯 필드만 남긴다.

        LLM 상담 분석이 슬롯키가 아닌 서술형 문장(예: '간판 허가·신고 필요 여부')을
        반환하는 경우를 걸러내, 의미 없는 후속 질문과 무한 루프를 막는다.
        """
        known = {item["field"] for item in QUESTION_BANK}
        answered = set(case["questionLoop"]["answeredFields"])
        filtered: list[str] = []
        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        text = f"{case.get('rawInput') or ''} {slot_value(case, 'business_activity') or ''}"
        user_answered_conditions = "condition_screening" in answered
        has_signage = self.documents.has_affirmative_signage(
            case,
            text,
            conditions,
            user_answered_conditions,
            "signboard_planned" in answered,
        )
        has_outdoor = self.documents.has_affirmative_outdoor(
            case,
            text,
            conditions,
            user_answered_conditions,
            "outdoor_space_planned" in answered,
        )
        signage_detail_fields = {"signboard_type", "signboard_size", "signboard_location", "signboard_image"}
        outdoor_detail_fields = {"outdoor_location", "outdoor_area"}
        for field in fields:
            if field not in known or field in answered or field in SYSTEM_DERIVED_FIELDS:
                continue
            if self.documents.is_signage_only_case(case) and field not in SIGNAGE_ONLY_ALLOWED_FIELDS:
                continue
            if self.documents.is_transfer_case(case) and field in TRANSFER_SKIP_FIELDS:
                continue
            if field in signage_detail_fields and not has_signage:
                continue
            if field in outdoor_detail_fields and not has_outdoor:
                continue
            if field == "owner_consent" and not (has_signage or has_outdoor):
                continue
            if field == "floor_unit" and self.floor_unit_known(case):
                continue
            if field == "signboard_planned" and "signage_planned" in conditions:
                continue
            if field == "outdoor_space_planned" and "outdoor_space_planned" in conditions:
                continue
            if field in case["slots"] and slot_value(case, field) not in (None, "", "unknown", []):
                continue
            append_unique(filtered, field)
        return filtered

    def apply_slot_answer(self, case: dict[str, Any], input_payload: dict[str, Any]) -> None:
        loop = case["questionLoop"]
        current = loop.get("current") or {}
        field = input_payload.get("fieldKey") or current.get("field")
        if not field:
            return

        answer_text, value, is_unknown, is_invalid = self.parse_answer(field, input_payload, current)
        question_text = current.get("question") or field

        if is_invalid and loop["attempts"].get(field, 0) < loop["maxAttemptsPerField"]:
            current["validationMessage"] = "답변을 확인하기 어려워요. 아는 만큼만 적거나 ‘아직 몰라요’를 눌러주세요."
            loop["current"] = current
            loop["retryCurrent"] = True
            self.record_question_ask(loop, field)
            return

        if is_unknown or is_invalid:
            append_unique(loop["unknownFields"], field)
            loop["answers"][field] = "unknown"
            set_slot(case, field, "unknown", "미정", admin_term_for(field, "unknown"), status="unknown")
        else:
            append_unique(loop["answeredFields"], field)
            loop["answers"][field] = value
            set_slot(case, field, value, answer_text, admin_term_for(field, value))
            if field == "condition_screening" and isinstance(value, list):
                for item in value:
                    append_condition(case, item)
            if field == "floor_unit":
                self.merge_floor_unit_into_address(case, str(value))
            if field == "signboard_planned" and value is True:
                append_condition(case, "signage_planned")
            if field == "outdoor_space_planned" and value is True:
                append_condition(case, "outdoor_space_planned")
            if field in {"signboard_type", "signboard_size", "signboard_location", "signboard_image"}:
                append_condition(case, "signage_planned")
            if field in {"outdoor_location", "outdoor_area"}:
                append_condition(case, "outdoor_space_planned")
            self.capture_client_building_ledger(case, input_payload)

        case["answers"].append({
            "id": f"answer_{uuid4().hex[:10]}",
            "field": field,
            "question": question_text,
            "answer": answer_text,
            "createdAt": now_iso(),
        })

    def parse_answer(self, field: str, payload: dict[str, Any], current: dict[str, Any]) -> tuple[str, Any, bool, bool]:
        option_ids = payload.get("optionIds") or []
        text = (payload.get("text") or payload.get("value") or "").strip()
        is_unknown = bool(payload.get("unknown")) or "unknown" in option_ids or self.is_unknown_text(text)

        if is_unknown:
            return "미정", "unknown", True, False

        if current.get("inputMode") == "free_text":
            if not text:
                return "미정", "unknown", True, False
            if not self.is_meaningful_text(text):
                return text, text, False, True
            return text, self.normalize_free_text_value(field, text), False, False

        value_map = FIELD_VALUE_MAP.get(field, {})
        values = [value_map.get(option_id, option_id) for option_id in option_ids if option_id != "unknown"]
        if not values:
            return "미정", "unknown", True, False

        labels = {
            option["id"]: option["title"]
            for option in current.get("options", [])
        }
        answer_text = " + ".join(labels.get(option_id, option_id) for option_id in option_ids if option_id != "unknown")
        return answer_text, values if len(values) > 1 else values[0], False, False

    @staticmethod
    def normalize_free_text_value(field: str, text: str) -> Any:
        if field == "exact_address" and re.search(r"미정|모름|몰라|아직", text):
            return "unknown"
        return text

    @staticmethod
    def merge_floor_unit_into_address(case: dict[str, Any], value: str) -> None:
        if not value or value == "unknown":
            return
        address = str(slot_value(case, "exact_address") or "").strip()
        if not address or value in address:
            return
        merged = f"{address}, {value}"
        set_slot(case, "exact_address", merged, merged, "도로명/지번 주소 + 층/호수")

    @classmethod
    def capture_client_building_ledger(cls, case: dict[str, Any], input_payload: dict[str, Any]) -> None:
        building = input_payload.get("building")
        if not isinstance(building, dict):
            return

        summary = cls.summarize_client_building_ledger(building)
        if not summary:
            return

        address = input_payload.get("address") if isinstance(input_payload.get("address"), dict) else {}
        case["clientBuildingLedger"] = {
            "status": "ok",
            "source": "frontend_building_api",
            "roadAddr": address.get("roadAddress") or "",
            "jibunAddr": address.get("jibunAddress") or "",
            "summary": summary,
            "recordCounts": {
                key: len(cls.list_records((building.get("records") or {}).get(key)))
                for key in ("title", "floor", "unit", "landZone")
            },
        }

        if summary.get("mainPurpsCdNm") and not slot_value(case, "building_use"):
            set_slot(
                case,
                "building_use",
                summary["mainPurpsCdNm"],
                summary["mainPurpsCdNm"],
                "건축물대장 API 주용도",
            )
        if summary.get("areaM2") and not slot_value(case, "area"):
            set_slot(case, "area", f"{summary['areaM2']}㎡", f"{summary['areaM2']}㎡", "건축물대장 API 면적")

    @classmethod
    def summarize_client_building_ledger(cls, building: dict[str, Any]) -> dict[str, Any]:
        records = building.get("records") or {}
        title = cls.first_dict(cls.list_records(records.get("title")))
        floors = cls.list_records(records.get("floor"))
        units = cls.list_records(records.get("unit"))
        zones = cls.list_records(records.get("landZone"))

        summary: dict[str, Any] = {}
        main_use = cls.first_value([title, *floors, *units], "mainPurpsCdNm", "mainPurps", "purpsCdNm")
        etc_use = cls.first_value([title, *floors, *units], "etcPurps", "etcPurpsNm")
        violated = cls.first_value([title], "violYn", "violtYn", "violated")
        area = cls.first_value([*units, *floors, title], "area", "areaM2", "totArea")

        if main_use:
            summary["mainPurpsCdNm"] = main_use
        if etc_use:
            summary["etcPurps"] = etc_use
        if violated not in (None, "", []):
            summary["violated"] = violated
        if area not in (None, "", []):
            summary["areaM2"] = area

        floor_uses = cls.floor_use_texts(floors) or cls.floor_use_texts(units)
        if floor_uses:
            summary["floorUses"] = floor_uses

        land_zones = cls.zone_texts(zones)
        if land_zones:
            summary["landZones"] = land_zones

        return summary

    @staticmethod
    def list_records(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if value in (None, "", []):
            return []
        return [value]

    @staticmethod
    def first_dict(records: list[Any]) -> dict[str, Any]:
        return next((item for item in records if isinstance(item, dict)), {})

    @classmethod
    def first_value(cls, records: list[Any], *keys: str) -> Any:
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in keys:
                value = record.get(key)
                if value not in (None, "", []):
                    return value
        return None

    @classmethod
    def floor_use_texts(cls, records: list[Any]) -> list[str]:
        texts: list[str] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            bits = [
                str(record.get("flrNoNm") or record.get("floor") or record.get("hoNm") or "").strip(),
                str(record.get("mainPurpsCdNm") or record.get("mainPurps") or "").strip(),
                str(record.get("etcPurps") or "").strip(),
            ]
            text = " ".join(bit for bit in bits if bit)
            if text and text not in texts:
                texts.append(text)
        return texts[:8]

    @staticmethod
    def zone_texts(records: list[Any]) -> list[str]:
        texts: list[str] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            text = str(
                record.get("jijiguCdNm")
                or record.get("jijiguGbCdNm")
                or record.get("etcJijigu")
                or record.get("landUseZone")
                or ""
            ).strip()
            if text and text not in texts:
                texts.append(text)
        return texts[:8]

    @staticmethod
    def is_unknown_text(text: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        return compact in {"미정", "모름", "몰라요", "아직몰라요", "아직몰라", "정하지않았어요"}

    @staticmethod
    def is_meaningful_text(text: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        if len(compact) < 2:
            return False
        if compact.lower() in {"asdf", "qwer", "test", "테스트"}:
            return False
        return bool(re.search(r"[가-힣0-9]", text))

    def add_followup_questions(self, case: dict[str, Any], fields: list[str]) -> None:
        loop = case["questionLoop"]
        loop["status"] = "idle"
        loop["current"] = None
        for field in fields:
            if field in SYSTEM_DERIVED_FIELDS:
                continue
            if field in loop["answeredFields"]:
                continue
            source = next((item for item in QUESTION_BANK if item["field"] == field), None)
            if not source:
                source = {
                    "field": field,
                    "label": field,
                    "question": f"{field} 정보를 알려주세요.",
                    "why": "새로 확인이 필요해요.",
                    "inputMode": "free_text",
                    "required": True,
                }
            if not any(item["field"] == field for item in loop["pendingQuestions"]):
                loop["pendingQuestions"].append(deepcopy(source))
            if field in loop["unknownFields"]:
                loop["unknownFields"].remove(field)

    def add_edit_questions(self, case: dict[str, Any], fields: list[str]) -> None:
        loop = case["questionLoop"]
        loop["status"] = "idle"
        loop["current"] = None
        loop["stopReason"] = ""
        loop["maxTotalQuestions"] = max(loop["maxTotalQuestions"], loop["totalAsked"] + len(fields) + 2)
        for field in fields:
            if field in SYSTEM_DERIVED_FIELDS:
                continue
            for bucket in ("answeredFields", "unknownFields", "skippedFields"):
                if field in loop[bucket]:
                    loop[bucket].remove(field)
            source = next((item for item in QUESTION_BANK if item["field"] == field), None)
            if source:
                loop["pendingQuestions"].append(deepcopy(source))


question_planner = QuestionPlanner()
