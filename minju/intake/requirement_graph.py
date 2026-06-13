from __future__ import annotations

from typing import Any

from schedule_planner import enrich_requirement_graph_schedule


GRAPH_VERSION = "heogaon.requirement_graph.v1"


DOCUMENTS: dict[str, dict[str, Any]] = {
    "food_business_report": {"label": "식품 영업 신고서", "stage": "before_business_report", "category": "food_business"},
    "hygiene_training": {"label": "위생교육 수료증", "stage": "before_business_report", "category": "food_business"},
    "health_certificate": {"label": "건강진단결과서", "stage": "before_business_report", "category": "food_business"},
    "lease_contract": {"label": "임대차계약서 또는 사용권한 증빙", "stage": "before_business_report", "category": "food_business"},
    "id_card": {"label": "신분증", "stage": "before_business_report", "category": "food_business"},
    "fire_safety_certificate": {
        "label": "소방완비증명서",
        "stage": "before_business_report",
        "category": "conditional_fire",
        "conditionText": "지하 66㎡ 이상 또는 지상 2층 이상 100㎡ 이상인 경우",
    },
    "lpg_completion_certificate": {
        "label": "액화석유가스 사용시설완성검사증명서",
        "stage": "before_business_report",
        "category": "conditional_lpg",
        "conditionText": "LPG 등 액화석유가스 사용시설의 완성검사 대상인 경우",
    },
    "business_registration": {"label": "사업자등록증", "stage": "after_business_report", "category": "business_registration"},
    "signboard_application": {"label": "옥외광고물 표시허가 신청서 또는 신고서", "stage": "before_or_during_opening", "category": "signboard"},
    "signboard_owner_consent": {"label": "건물/대지 사용 승낙서", "stage": "before_or_during_opening", "category": "signboard"},
    "signboard_photo_design": {"label": "간판 설치 위치 사진, 원색도안, 설계도", "stage": "before_or_during_opening", "category": "signboard"},
    "outdoor_space_materials": {"label": "외부공간 위치도, 현장 사진, 사용 면적 도면", "stage": "before_or_during_opening", "category": "outdoor_space"},
    "outdoor_owner_consent": {"label": "소유자/관리인 사용 승낙서", "stage": "before_or_during_opening", "category": "outdoor_space"},
    "building_ledger_result": {"label": "건축물대장 열람/조회 결과", "stage": "precheck", "category": "building_use"},
    "same_place_history_result": {"label": "동일 장소 기존 업소/행정처분 이력 조회 결과", "stage": "precheck", "category": "same_place_history"},
}


DEPARTMENTS: dict[str, dict[str, str]] = {
    "food_hygiene": {"label": "위생과 또는 식품위생 인허가 담당"},
    "building": {"label": "건축과 또는 건축물대장 담당"},
    "signboard": {"label": "옥외광고물/도시경관 담당"},
    "road_occupancy": {"label": "도로관리/건설관리 담당"},
    "fire_safety": {"label": "관할 소방서 또는 가스안전 검사 담당"},
}


ACTION_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "open_food_business": {
        "label": "식품접객업 창업/영업신고",
        "documents": [
            "food_business_report",
            "hygiene_training",
            "health_certificate",
            "lease_contract",
            "id_card",
            "fire_safety_certificate",
            "lpg_completion_certificate",
            "business_registration",
        ],
        "departments": ["food_hygiene"],
        "requiredInputs": ["business_type", "base_address", "floor_unit", "area", "liquor_sales"],
    },
    "check_building_use": {
        "label": "건축물 용도/위반건축물 확인",
        "documents": ["building_ledger_result"],
        "departments": ["building"],
        "requiredInputs": ["base_address", "floor_unit", "business_type"],
    },
    "check_same_place_history": {
        "label": "동일 장소 인허가/행정처분 이력 확인",
        "documents": ["same_place_history_result"],
        "departments": ["food_hygiene"],
        "requiredInputs": ["base_address", "floor_unit", "business_type"],
    },
    "install_signboard": {
        "label": "간판 설치/변경",
        "documents": ["signboard_application", "signboard_owner_consent", "signboard_photo_design"],
        "departments": ["signboard"],
        "requiredInputs": ["base_address", "signboard_type", "signboard_size", "signboard_location", "owner_consent"],
    },
    "use_outdoor_space": {
        "label": "외부 테이블/테라스/도로점용",
        "documents": ["outdoor_space_materials", "outdoor_owner_consent"],
        "departments": ["road_occupancy"],
        "requiredInputs": ["base_address", "outdoor_location", "outdoor_area", "owner_consent"],
    },
    "lpg_facility_completion": {
        "label": "LPG/가스 사용시설 완성검사",
        "documents": ["lpg_completion_certificate"],
        "departments": ["fire_safety"],
        "requiredInputs": ["base_address", "lpg_use"],
    },
    "document_readiness": {
        "label": "제출 서류 준비상태 점검",
        "documents": [],
        "departments": ["food_hygiene"],
        "requiredInputs": ["business_type"],
    },
    "change_food_business": {
        "label": "기존 식품접객업 변경/추가",
        "documents": ["building_ledger_result"],
        "departments": ["food_hygiene", "building"],
        "requiredInputs": ["business_type", "base_address", "floor_unit", "liquor_sales"],
    },
}


def infer_scope(slots: dict[str, Any]) -> str:
    intent = slots.get("intent")
    if intent == "food_business_precheck":
        return "full_opening"
    if intent in {"signboard_permit_check", "outdoor_space_permit_check", "building_use_check"}:
        return "specific_check"
    if intent == "takeover_history_check":
        return "takeover_or_history"
    if intent == "document_readiness_check":
        return "document_status"
    if intent == "business_change_check":
        return "partial_change"
    return "unknown"


def infer_action_status(slots: dict[str, Any]) -> dict[str, str]:
    intent = slots.get("intent")
    facility = slots.get("facility", {})
    statuses: dict[str, str] = {}

    if intent == "food_business_precheck":
        statuses["open_food_business"] = "active"
        statuses["check_building_use"] = "active"
        statuses["check_same_place_history"] = "active"
        statuses["install_signboard"] = "active" if facility.get("signboard") is True else "conditional_if_planned"
        statuses["use_outdoor_space"] = "active" if facility.get("outdoorSpace") is True else "conditional_if_planned"
        statuses["lpg_facility_completion"] = "active" if facility.get("lpgUse") is True else "not_required_now"
        if facility.get("signboard") is False:
            statuses["install_signboard"] = "not_required_now"
        if facility.get("outdoorSpace") is False:
            statuses["use_outdoor_space"] = "not_required_now"
    elif intent == "signboard_permit_check":
        statuses["install_signboard"] = "active"
    elif intent == "outdoor_space_permit_check":
        statuses["use_outdoor_space"] = "active"
    elif intent == "building_use_check":
        statuses["check_building_use"] = "active"
    elif intent == "takeover_history_check":
        statuses["check_same_place_history"] = "active"
    elif intent == "document_readiness_check":
        statuses["document_readiness"] = "active"
        statuses["open_food_business"] = "reference"
    elif intent == "business_change_check":
        statuses["change_food_business"] = "active"
        if facility.get("signboard") is True:
            statuses["install_signboard"] = "active"
        if facility.get("outdoorSpace") is True:
            statuses["use_outdoor_space"] = "active"
        if facility.get("lpgUse") is True:
            statuses["lpg_facility_completion"] = "active"

    return statuses


def slot_presence(slots: dict[str, Any]) -> dict[str, bool]:
    address = slots.get("address", {})
    business = slots.get("business", {})
    space = slots.get("space", {})
    facility = slots.get("facility", {})
    property_rights = slots.get("propertyRights", {})
    return {
        "business_type": bool(business.get("requestedType") or business.get("candidateTypes")),
        "base_address": bool(address.get("lookupAddress") or address.get("full")),
        "floor_unit": bool(address.get("hasFloor") or address.get("hasUnit")),
        "area": space.get("areaM2") is not None,
        "liquor_sales": business.get("liquorSales") is not None,
        "signboard_type": bool(facility.get("signboardType")),
        "signboard_size": bool(facility.get("signboardSizeText")),
        "signboard_location": facility.get("signboard") is True,
        "outdoor_location": facility.get("outdoorLocation") not in (None, "", "unknown"),
        "outdoor_area": bool(facility.get("outdoorAreaText") or facility.get("outdoorTableCount")),
        "owner_consent": property_rights.get("managerConsentKnown") == "yes" or property_rights.get("leaseOrOwnershipStatus") == "owner",
        "lpg_use": facility.get("lpgUse") is not None,
    }


def evaluate_fire_document(slots: dict[str, Any]) -> dict[str, Any]:
    doc = DOCUMENTS["fire_safety_certificate"]
    space = slots.get("space", {})
    area = space.get("areaM2")
    is_basement = space.get("isBasement")
    is_second_floor_or_higher = space.get("isSecondFloorOrHigher")
    missing = []
    if area is None:
        missing.append("area")
    if is_basement is None and is_second_floor_or_higher is None:
        missing.append("floor_unit")
    if missing:
        return {
            "id": "fire_safety_certificate",
            "label": doc["label"],
            "status": "needs_input",
            "condition": doc["conditionText"],
            "missingInputs": missing,
            "stage": doc["stage"],
        }
    required = (is_basement is True and area >= 66) or (is_second_floor_or_higher is True and area >= 100)
    return {
        "id": "fire_safety_certificate",
        "label": doc["label"],
        "status": "required" if required else "not_required_by_current_inputs",
        "condition": doc["conditionText"],
        "missingInputs": [],
        "stage": doc["stage"],
    }


def evaluate_lpg_document(slots: dict[str, Any]) -> dict[str, Any]:
    doc = DOCUMENTS["lpg_completion_certificate"]
    facility = slots.get("facility", {})
    lpg_use = facility.get("lpgUse")
    if lpg_use is True:
        status = "required"
    elif facility.get("cookingFire") is True:
        status = "needs_input"
    else:
        status = "not_required_by_current_inputs"
    return {
        "id": "lpg_completion_certificate",
        "label": doc["label"],
        "status": status,
        "condition": doc["conditionText"],
        "missingInputs": ["lpg_use"] if status == "needs_input" else [],
        "stage": doc["stage"],
    }


def evaluate_document(doc_id: str, slots: dict[str, Any], action_status: str) -> dict[str, Any]:
    if doc_id == "fire_safety_certificate":
        item = evaluate_fire_document(slots)
    elif doc_id == "lpg_completion_certificate":
        item = evaluate_lpg_document(slots)
    else:
        doc = DOCUMENTS[doc_id]
        status = "later" if doc["stage"] == "after_business_report" else "required"
        item = {
            "id": doc_id,
            "label": doc["label"],
            "status": status,
            "condition": doc.get("conditionText", ""),
            "missingInputs": [],
            "stage": doc["stage"],
        }
    if action_status == "conditional_if_planned" and item["status"] == "required":
        item["status"] = "conditional_if_planned"
    if action_status == "reference" and item["status"] == "required":
        item["status"] = "reference"
    return item


def collect_departments(action_statuses: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    primary: list[dict[str, str]] = []
    conditional: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for action_id, status in action_statuses.items():
        action = ACTION_REQUIREMENTS.get(action_id)
        if not action:
            continue
        for department_id in action.get("departments", []):
            key = (department_id, status)
            if key in seen:
                continue
            seen.add(key)
            item = {
                "id": department_id,
                "label": DEPARTMENTS[department_id]["label"],
                "because": action["label"],
                "status": "primary" if status in {"active", "reference"} else status,
            }
            if status in {"active", "reference"}:
                primary.append(item)
            elif status == "conditional_if_planned":
                conditional.append(item)
    return {"primary": primary, "conditional": conditional}


def collect_missing_inputs(action_statuses: dict[str, str], slots: dict[str, Any]) -> list[dict[str, Any]]:
    presence = slot_presence(slots)
    missing_by_id: dict[str, dict[str, Any]] = {}
    for action_id, status in action_statuses.items():
        if status not in {"active", "reference"}:
            continue
        action = ACTION_REQUIREMENTS.get(action_id)
        if not action:
            continue
        for input_id in action.get("requiredInputs", []):
            if presence.get(input_id):
                continue
            missing_by_id.setdefault(input_id, {"id": input_id, "requiredBy": [], "reason": "그래프 요구사항 계산 결과 필요한 입력입니다."})
            missing_by_id[input_id]["requiredBy"].append(action_id)
    return list(missing_by_id.values())


def document_labels(document_list: list[dict[str, Any]], doc_ids: list[str]) -> list[str]:
    by_id = {item.get("id"): item for item in document_list}
    return [
        by_id[doc_id]["label"]
        for doc_id in doc_ids
        if doc_id in by_id and by_id[doc_id].get("status") != "not_required_by_current_inputs"
    ]


def active_or_reference(action_statuses: dict[str, str], action_id: str) -> bool:
    return action_statuses.get(action_id) in {"active", "reference"}


def active_or_conditional(action_statuses: dict[str, str], action_id: str) -> bool:
    return action_statuses.get(action_id) in {"active", "conditional_if_planned"}


def build_procedure_plan(scope: str, action_statuses: dict[str, str], document_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the recommended operational order, separate from document buckets."""
    steps: list[dict[str, Any]] = []

    def add(
        id_: str,
        title: str,
        timing: str,
        actions: list[str],
        documents: list[str],
        departments: list[str],
        status: str = "active",
        notes: list[str] | None = None,
    ) -> None:
        steps.append(
            {
                "order": len(steps) + 1,
                "id": id_,
                "title": title,
                "timing": timing,
                "status": status,
                "actions": actions,
                "documents": document_labels(document_list, documents),
                "departments": departments,
                "notes": notes or [],
            }
        )

    if scope == "full_opening":
        add(
            "precheck_building_and_history",
            "건축물대장, 위반건축물, 동일 장소 이력 먼저 확인",
            "영업신고 서류를 확정하기 전",
            ["check_building_use", "check_same_place_history"],
            ["building_ledger_result", "same_place_history_result"],
            ["건축과/건축물대장 담당", "위생과/식품위생 담당"],
            notes=["건축물 용도와 과거 행정처분 이력이 막히면 뒤 서류 준비가 헛돌 수 있습니다."],
        )
        add(
            "confirm_food_business_route",
            "업종 경로 확정",
            "사전 검증 직후",
            ["open_food_business"],
            [],
            ["위생과/식품위생 담당"],
            notes=["카페 표현은 휴게음식점 후보지만, 조리 방식이나 주류 계획에 따라 일반음식점 후보도 함께 검토합니다."],
        )
        add(
            "prepare_before_business_report_documents",
            "영업신고 전 필수서류 준비",
            "영업신고 접수 전",
            ["open_food_business"],
            ["hygiene_training", "health_certificate", "lease_contract", "id_card", "fire_safety_certificate", "lpg_completion_certificate"],
            ["위생과/식품위생 담당", "관할 소방서"],
            notes=["소방완비증명서는 지하 66㎡ 이상 또는 지상 2층 100㎡ 이상 등 조건에 따라 필요합니다.", "LPG 등 가스 사용시설이면 완성검사증명서 대상 여부를 함께 확인합니다."],
        )
        if active_or_conditional(action_statuses, "install_signboard"):
            add(
                "signboard_permit_or_report",
                "간판 허가/신고 병행 확인",
                "영업신고 전 또는 개업 전",
                ["install_signboard"],
                ["signboard_application", "signboard_owner_consent", "signboard_photo_design"],
                ["옥외광고물/도시경관 담당"],
                status=action_statuses.get("install_signboard", "conditional_if_planned"),
                notes=["간판은 식품 영업신고와 담당 부서가 다르므로 개업 전 별도로 확인합니다."],
            )
        if active_or_conditional(action_statuses, "use_outdoor_space"):
            add(
                "outdoor_space_or_road_occupancy",
                "외부공간/도로점용 가능 여부 확인",
                "외부 테이블을 둘 계획이 있을 때",
                ["use_outdoor_space"],
                ["outdoor_space_materials", "outdoor_owner_consent"],
                ["도로관리/건설관리 담당"],
                status=action_statuses.get("use_outdoor_space", "conditional_if_planned"),
                notes=["사유지인지 보도/도로인지에 따라 제출처와 허가 성격이 달라집니다."],
            )
        add(
            "submit_food_business_report",
            "영업신고 접수 및 영업신고증 발급",
            "사업자등록 전에 먼저",
            ["open_food_business"],
            ["food_business_report"],
            ["위생과/식품위생 담당"],
            notes=["사업자등록보다 영업신고증 발급이 먼저입니다."],
        )
        add(
            "business_registration_after_report",
            "사업자등록",
            "영업신고증 발급 후, 사업개시일부터 20일 내",
            ["open_food_business"],
            ["business_registration"],
            ["관할 세무서/홈택스"],
            status="later",
            notes=["식품접객업은 영업신고증을 받은 뒤 사업자등록으로 넘어가는 순서가 자연스럽습니다."],
        )
        return steps

    if active_or_reference(action_statuses, "document_readiness"):
        add(
            "check_prepared_documents",
            "준비된 서류와 부족 서류 분리",
            "접수 전",
            ["document_readiness"],
            ["hygiene_training", "health_certificate", "lease_contract", "id_card", "fire_safety_certificate"],
            ["위생과/식품위생 담당"],
            notes=["서류 점검만 하는 경우에는 건축물대장/API 판단보다 현재 준비상태 정리가 우선입니다."],
        )

    if active_or_reference(action_statuses, "check_building_use"):
        add(
            "check_building_use",
            "건축물대장으로 용도/위반건축물 확인",
            "다른 접수 전",
            ["check_building_use"],
            ["building_ledger_result"],
            ["건축과/건축물대장 담당"],
        )

    if active_or_reference(action_statuses, "check_same_place_history"):
        add(
            "check_same_place_history",
            "동일 장소 기존 업소/행정처분 이력 확인",
            "인수 또는 같은 장소 재창업 전",
            ["check_same_place_history"],
            ["same_place_history_result"],
            ["위생과/식품위생 담당"],
        )

    if active_or_reference(action_statuses, "change_food_business"):
        add(
            "change_food_business",
            "기존 영업 변경 가능성 확인",
            "변경 신고/전환 전",
            ["change_food_business"],
            ["building_ledger_result"],
            ["위생과/식품위생 담당", "건축과/건축물대장 담당"],
        )

    if active_or_reference(action_statuses, "install_signboard"):
        add(
            "signboard_permit_or_report",
            "간판 허가/신고 확인",
            "설치 전",
            ["install_signboard"],
            ["signboard_application", "signboard_owner_consent", "signboard_photo_design"],
            ["옥외광고물/도시경관 담당"],
        )

    if active_or_reference(action_statuses, "use_outdoor_space"):
        add(
            "outdoor_space_or_road_occupancy",
            "외부공간/도로점용 확인",
            "외부 테이블 설치 전",
            ["use_outdoor_space"],
            ["outdoor_space_materials", "outdoor_owner_consent"],
            ["도로관리/건설관리 담당"],
        )

    return steps


def build_requirement_graph(slots: dict[str, Any]) -> dict[str, Any]:
    scope = infer_scope(slots)
    action_statuses = infer_action_status(slots)
    edges: list[dict[str, str]] = []
    documents: dict[str, dict[str, Any]] = {}
    activated_actions = []

    for action_id, status in action_statuses.items():
        action = ACTION_REQUIREMENTS.get(action_id)
        if not action:
            continue
        activated_actions.append({"id": action_id, "label": action["label"], "status": status})
        edges.append({"from": scope, "to": action_id, "type": status})
        for doc_id in action.get("documents", []):
            doc_item = evaluate_document(doc_id, slots, status)
            previous = documents.get(doc_id)
            if previous is None or previous["status"] in {"conditional_if_planned", "reference", "later"}:
                documents[doc_id] = doc_item
            edges.append({"from": action_id, "to": doc_id, "type": "requires_document"})

    document_list = list(documents.values())
    graph = {
        "version": GRAPH_VERSION,
        "scope": scope,
        "graphLogic": {
            "principle": "AI가 서류를 추측하지 않고, scope/action 노드에서 requirement 노드로 그래프를 펼쳐 계산합니다.",
            "fullOpeningPolicy": "full_opening은 영업신고 핵심 서류와 건축물/동일장소 확인을 항상 펼치고, 간판/외부공간은 입력 여부에 따라 확정 또는 조건부로 둡니다.",
        },
        "activatedActions": activated_actions,
        "edges": edges,
        "documentPlan": {
            "requiredForSubmission": [item for item in document_list if item["status"] == "required"],
            "conditional": [item for item in document_list if item["status"] in {"needs_input", "conditional_if_planned"}],
            "later": [item for item in document_list if item["status"] in {"later", "reference"}],
            "notRequiredByCurrentInputs": [item for item in document_list if item["status"] == "not_required_by_current_inputs"],
        },
        "departmentPlan": collect_departments(action_statuses),
        "missingInputs": collect_missing_inputs(action_statuses, slots),
        "procedurePlan": build_procedure_plan(scope, action_statuses, document_list),
    }
    return enrich_requirement_graph_schedule(graph)
