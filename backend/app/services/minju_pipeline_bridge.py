from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.slot_utils import append_condition, as_list, set_slot, slot_value


def _load_build_intake_result():
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from minju.intake.intake_pipeline import build_intake_result
    except Exception as exc:  # pragma: no cover - reported through case state
        return None, f"{type(exc).__name__}: {exc}"
    return build_intake_result, ""


class MinjuPipelineBridge:
    """Attach the richer minju intake/API/judgement result to the V2 case flow."""

    def bootstrap(self, case: dict[str, Any]) -> None:
        build_intake_result, import_error = _load_build_intake_result()
        if import_error or build_intake_result is None:
            self._store_error(case, "import_failed", import_error, target="minjuDraft")
            return

        self._ensure_gms_env()
        text = str(case.get("rawInput") or "").strip()
        if not text:
            return

        sync_key = json.dumps(
            {
                "text": text,
                "slotProvider": self.slot_provider,
                "runDecision": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if (case.get("minjuDraft") or {}).get("syncKey") == sync_key:
            return

        try:
            result = build_intake_result(
                text,
                run_decision=False,
                slot_provider=self.slot_provider,
                fallback_to_rule=True,
                judgement_provider="rule",
                judgement_fallback_to_rule=True,
                inquiry_provider="rule",
                inquiry_fallback_to_rule=True,
            )
        except Exception as exc:  # pragma: no cover - surfaced in UI metadata
            self._store_error(case, "bootstrap_failed", f"{type(exc).__name__}: {exc}", target="minjuDraft")
            return

        case["minjuDraft"] = {
            "status": "ok",
            "syncKey": sync_key,
            "inputText": text,
            "providers": {
                "slot": self.slot_provider,
                "judgement": "rule",
                "inquiry": "rule",
            },
            "summary": self._compact_result(result),
        }
        self.apply_slots_to_case(case, result.get("slots") or {})
        case.setdefault("ai", {})["minjuDraftSource"] = "minju.intake"

    def sync(self, case: dict[str, Any]) -> None:
        build_intake_result, import_error = _load_build_intake_result()
        if import_error or build_intake_result is None:
            self._store_error(case, "import_failed", import_error)
            return

        self._ensure_gms_env()
        text = self._case_text(case)
        judgement_provider = self.judgement_provider_for_case(case)
        inquiry_provider = self.inquiry_provider_for_case(case)
        sync_key = json.dumps(
            {
                "text": text,
                "slotProvider": self.slot_provider,
                "judgementProvider": judgement_provider,
                "inquiryProvider": inquiry_provider,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if (case.get("minjuIntake") or {}).get("syncKey") == sync_key:
            return

        try:
            result = build_intake_result(
                text,
                run_decision=True,
                slot_provider=self.slot_provider,
                fallback_to_rule=True,
                judgement_provider=judgement_provider,
                judgement_fallback_to_rule=True,
                inquiry_provider=inquiry_provider,
                inquiry_fallback_to_rule=True,
            )
        except Exception as exc:  # pragma: no cover - surfaced in UI metadata
            self._store_error(case, "pipeline_failed", f"{type(exc).__name__}: {exc}")
            return

        case["minjuIntake"] = {
            "status": "ok",
            "syncKey": sync_key,
            "inputText": text,
            "providers": {
                "slot": self.slot_provider,
                "judgement": judgement_provider,
                "inquiry": inquiry_provider,
            },
            "summary": self._compact_result(result),
        }
        self.apply_slots_to_case(case, result.get("slots") or {})
        self.apply_external_checks_to_case(case, result.get("externalChecks") or {})
        case.setdefault("ai", {})["minjuPipelineSource"] = "minju.intake"

    @property
    def slot_provider(self) -> str:
        if os.getenv("MINJU_SLOT_PROVIDER"):
            return os.getenv("MINJU_SLOT_PROVIDER", "rule").strip().lower()
        return "gms" if settings.llm_available else "rule"

    def judgement_provider_for_case(self, case: dict[str, Any]) -> str:
        if os.getenv("MINJU_JUDGEMENT_PROVIDER"):
            return os.getenv("MINJU_JUDGEMENT_PROVIDER", "rule").strip().lower()
        return "gms" if settings.llm_available else "rule"

    def inquiry_provider_for_case(self, case: dict[str, Any]) -> str:
        if os.getenv("MINJU_INQUIRY_PROVIDER"):
            return os.getenv("MINJU_INQUIRY_PROVIDER", "rule").strip().lower()
        return "rule"

    @staticmethod
    def _ensure_gms_env() -> None:
        if settings.llm_api_key:
            os.environ.setdefault("GMS_API_KEY", settings.llm_api_key)
            os.environ.setdefault("HEOGAON_GMS_API_KEY", settings.llm_api_key)
        os.environ.setdefault("GMS_MODEL", settings.llm_model)
        os.environ.setdefault("HEOGAON_GMS_MODEL", settings.llm_model)
        os.environ.setdefault("GMS_BASE_URL", settings.llm_base_url)
        os.environ.setdefault("HEOGAON_GMS_BASE_URL", settings.llm_base_url)

    @staticmethod
    def apply_slots_to_case(case: dict[str, Any], slots: dict[str, Any]) -> None:
        address = slots.get("address") or {}
        business = slots.get("business") or {}
        space = slots.get("space") or {}
        facility = slots.get("facility") or {}
        documents = slots.get("documents") or {}

        if address.get("raw") and "location" not in case["slots"]:
            set_slot(case, "location", address["raw"], address["raw"], "AI 추출 지역")
        if address.get("full") and "exact_address" not in case["slots"]:
            set_slot(case, "exact_address", address["full"], address["full"], "AI 추출 주소")
        if address.get("detail") and "floor_unit" not in case["slots"]:
            set_slot(case, "floor_unit", address["detail"], address["detail"], "AI 추출 층/호수")

        business_text = business.get("requestedType") or business.get("concept") or ""
        candidates = business.get("candidateTypes") or []
        if not business_text and candidates:
            business_text = " / ".join(str(item) for item in candidates[:2])
        if business_text and business_text != "unknown" and "business_activity" not in case["slots"]:
            set_slot(case, "business_activity", business_text, business_text, "AI 추출 업종/판매품목")

        if business.get("liquorSales") is not None and "liquor_sales" not in case["slots"]:
            value = bool(business.get("liquorSales"))
            set_slot(case, "liquor_sales", value, "주류 판매 예정" if value else "주류 판매 없음", "AI 추출 주류 판매 여부")

        area_text = ""
        if space.get("areaPyeong"):
            area_text = f"{space['areaPyeong']}평"
        elif space.get("areaM2"):
            area_text = f"{space['areaM2']}㎡"
        if area_text and "area" not in case["slots"]:
            set_slot(case, "area", area_text, area_text, "AI 추출 영업장 면적")

        if facility.get("cookingFire") is True and "manufacturing_or_simple_sale" not in case["slots"]:
            set_slot(case, "manufacturing_or_simple_sale", "cook", "매장 조리", "AI 추출 조리·제조 방식")
        if facility.get("seating") is True and "on_site_consumption" not in case["slots"]:
            set_slot(case, "on_site_consumption", True, "매장 취식 가능", "AI 추출 매장 취식 여부")
        if facility.get("takeoutOnly") is True and "on_site_consumption" not in case["slots"]:
            set_slot(case, "on_site_consumption", False, "포장·배달 위주", "AI 추출 매장 취식 여부")

        if facility.get("signboard") is True:
            set_slot(case, "signboard_planned", True, "간판 설치 예정", "AI 추출 간판 설치 여부")
            append_condition(case, "signage_planned")
        if facility.get("signboard") is False and "signboard_planned" not in case["slots"]:
            set_slot(case, "signboard_planned", False, "간판 설치 계획 없음", "AI 추출 간판 설치 여부")
        if facility.get("signboardType") and "signboard_type" not in case["slots"]:
            set_slot(case, "signboard_type", facility["signboardType"], facility["signboardType"], "AI 추출 간판 종류")
        if facility.get("signboardSizeText") and "signboard_size" not in case["slots"]:
            set_slot(case, "signboard_size", facility["signboardSizeText"], facility["signboardSizeText"], "AI 추출 간판 크기")

        if facility.get("outdoorSpace") is True:
            set_slot(case, "outdoor_space_planned", True, "외부공간 사용 예정", "AI 추출 외부공간 사용 여부")
            append_condition(case, "outdoor_space_planned")
        if facility.get("outdoorSpace") is False and "outdoor_space_planned" not in case["slots"]:
            set_slot(case, "outdoor_space_planned", False, "외부공간 사용 계획 없음", "AI 추출 외부공간 사용 여부")
        if facility.get("outdoorLocation") and facility.get("outdoorLocation") != "unknown" and "outdoor_location" not in case["slots"]:
            set_slot(case, "outdoor_location", facility["outdoorLocation"], facility["outdoorLocation"], "AI 추출 외부공간 위치")
        if facility.get("outdoorAreaText") and "outdoor_area" not in case["slots"]:
            set_slot(case, "outdoor_area", facility["outdoorAreaText"], facility["outdoorAreaText"], "AI 추출 외부공간 면적")

        for source, field in [
            ("leaseContract", "lease_contract"),
            ("hygieneTraining", "hygieneTraining"),
            ("healthCertificate", "healthCertificate"),
            ("fireCertificate", "fireCertificate"),
        ]:
            value = documents.get(source)
            if value and value != "unknown" and field not in case["slots"]:
                set_slot(case, field, value, value, "AI 추출 서류 준비상태")

    @staticmethod
    def apply_external_checks_to_case(case: dict[str, Any], external: dict[str, Any]) -> None:
        building = external.get("buildingLedger") or {}
        summary = building.get("summary") or {}
        area = summary.get("areaM2")
        if area not in (None, "", [], "unknown") and "area" not in case["slots"]:
            set_slot(case, "area", f"{area}㎡", f"{area}㎡", "건축물대장 API 면적")

    @staticmethod
    def _case_text(case: dict[str, Any]) -> str:
        lines: list[str] = []
        raw = str(case.get("rawInput") or "").strip()
        if raw:
            lines.append(raw)

        known_lines = []
        for label, value in [
            ("지역", slot_value(case, "location")),
            ("상세주소", slot_value(case, "exact_address")),
            ("업종/목적", slot_value(case, "business_activity")),
            ("영업장 면적", slot_value(case, "area")),
            ("조리/제조 방식", slot_value(case, "manufacturing_or_simple_sale")),
            ("기존 영업 인수 여부", slot_value(case, "takeover_type")),
        ]:
            if value not in (None, "", "unknown", []):
                known_lines.append(f"{label}: {value}")

        on_site = slot_value(case, "on_site_consumption")
        if on_site is not None:
            known_lines.append(f"매장 취식: {'있음' if on_site is True else '없음'}")

        liquor = slot_value(case, "liquor_sales")
        if liquor is not None:
            known_lines.append(f"주류 판매: {'예정' if liquor is True else '없음'}")

        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        if "signage_planned" in conditions:
            known_lines.append("간판 설치: 예정")
        if "outdoor_space_planned" in conditions:
            known_lines.append("가게 앞 테이블/외부공간 사용: 예정")
        if "lpg_use" in conditions:
            known_lines.append("LPG 사용: 예정")
        if "online_sales_planned" in conditions:
            known_lines.append("온라인 판매/배달: 예정")

        if known_lines:
            lines.append("[확인된 정보]\n" + "\n".join(known_lines))

        answer_lines = []
        for answer in case.get("answers") or []:
            field = answer.get("field")
            value = answer.get("answer")
            if field and value:
                answer_lines.append(f"{field}: {value}")
        if answer_lines:
            lines.append("[사용자 추가 답변]\n" + "\n".join(answer_lines[-8:]))

        return "\n\n".join(lines).strip()

    @staticmethod
    def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
        graph = result.get("requirementGraph") or {}
        document_plan = graph.get("documentPlan") or {}
        department_plan = graph.get("departmentPlan") or {}
        judgement = ((result.get("aiJudgement") or {}).get("judgement") or {})
        inquiry = result.get("inquiryPackage") or {}
        external = result.get("externalChecks") or {}
        building = external.get("buildingLedger") or {}
        decision = result.get("decisionEngine") or {}

        return {
            "status": result.get("status"),
            "slots": result.get("slots"),
            "missingInfo": result.get("missingInfo"),
            "apiPlan": result.get("apiPlan"),
            "externalChecks": {
                "status": external.get("status"),
                "addressForApi": external.get("addressForApi"),
                "buildingLedger": {
                    "status": building.get("status"),
                    "reason": building.get("reason"),
                    "roadAddr": building.get("roadAddr"),
                    "jibunAddr": building.get("jibunAddr"),
                    "summary": building.get("summary"),
                    "recordCounts": building.get("recordCounts"),
                },
                "pastBusinessLookup": external.get("pastBusinessLookup"),
            },
            "decisionEngine": {
                "status": decision.get("status"),
                "reason": decision.get("reason"),
                "mode": decision.get("mode"),
            },
            "requirementGraph": {
                "scope": graph.get("scope"),
                "activatedActions": graph.get("activatedActions") or [],
                "missingInputs": graph.get("missingInputs") or [],
                "procedurePlan": graph.get("procedurePlan") or [],
                "documentPlan": {
                    "requiredForSubmission": document_plan.get("requiredForSubmission") or [],
                    "conditional": document_plan.get("conditional") or [],
                    "later": document_plan.get("later") or [],
                },
                "departmentPlan": {
                    "primary": department_plan.get("primary") or [],
                    "conditional": department_plan.get("conditional") or [],
                    "later": department_plan.get("later") or [],
                },
            },
            "aiJudgement": {
                "meta": (result.get("aiJudgement") or {}).get("meta") or {},
                "decisionStatus": judgement.get("decisionStatus"),
                "confidence": judgement.get("confidence"),
                "summary": judgement.get("summary"),
                "canSayNow": judgement.get("canSayNow") or [],
                "cannotConfirmYet": judgement.get("cannotConfirmYet") or [],
                "questionsToAsk": judgement.get("questionsToAsk") or [],
                "apiChecks": judgement.get("apiChecks") or {},
                "documentSummary": judgement.get("documentSummary") or {},
                "departmentSummary": judgement.get("departmentSummary") or {},
                "finalResponseDraft": judgement.get("finalResponseDraft") or "",
            },
            "inquiryPackage": {
                "status": inquiry.get("status"),
                "district": inquiry.get("district"),
                "activeInquiry": inquiry.get("activeInquiry"),
                "contacts": inquiry.get("contacts") or [],
                "channels": inquiry.get("channels") or [],
                "documentGuides": inquiry.get("documentGuides") or [],
                "checkItems": inquiry.get("checkItems") or [],
                "scripts": inquiry.get("scripts") or {},
            },
        }

    @staticmethod
    def _store_error(case: dict[str, Any], reason: str, message: str, target: str = "minjuIntake") -> None:
        case[target] = {
            "status": "error",
            "reason": reason,
            "message": message,
            "summary": {},
        }
        warnings = case.setdefault("ai", {}).setdefault("warnings", [])
        warning = f"minju pipeline {reason}: {message}"
        if warning not in warnings:
            warnings.append(warning)


minju_pipeline_bridge = MinjuPipelineBridge()
