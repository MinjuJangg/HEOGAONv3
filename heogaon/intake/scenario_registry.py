from __future__ import annotations

from typing import Any


SCENARIOS: dict[str, dict[str, Any]] = {
    "food_business_precheck": {
        "title": "식품접객업 창업/영업신고 사전진단",
        "description": "카페, 커피숍, 일반음식점, 제과점 등 식품접객업을 새로 열거나 신고 전 가능성을 확인합니다.",
        "primarySlots": ["business.concept", "business.salesItems", "business.liquorSales", "space.areaM2", "location.roadOrLotAddress"],
        "requiredNow": ["business_concept", "sales_items", "liquor_sales", "area_if_known", "detailed_address_for_building_check"],
        "decisionModules": ["food_business_route", "building_use", "violation_building", "same_place_history", "documents", "departments"],
        "nextStage": "building_property_check",
    },
    "signboard_permit_check": {
        "title": "간판 설치/변경 허가ㆍ신고 확인",
        "description": "간판, 돌출간판, 입간판, 현수막 등 옥외광고물 표시허가 또는 신고 여부를 확인합니다.",
        "primarySlots": ["location.roadOrLotAddress", "facility.signboard", "signboard.type", "signboard.size", "propertyRights.managerConsentKnown"],
        "requiredNow": ["address", "signboard_type", "signboard_size"],
        "decisionModules": ["signboard_permit", "owner_consent", "department_guide"],
        "nextStage": "signboard_detail_screening",
    },
    "outdoor_space_permit_check": {
        "title": "외부 테이블/테라스 사용 확인",
        "description": "가게 앞 테이블, 테라스, 야장 등 외부공간 사용 시 도로점용 또는 사용권한 확인이 필요한지 봅니다.",
        "primarySlots": ["location.roadOrLotAddress", "facility.outdoorSpace", "outdoor.locationType", "outdoor.area"],
        "requiredNow": ["address", "outdoor_location", "outdoor_area"],
        "decisionModules": ["road_occupancy", "owner_consent", "department_guide"],
        "nextStage": "outdoor_space_detail_screening",
    },
    "business_change_check": {
        "title": "기존 업소 영업내용 변경 확인",
        "description": "기존 카페에서 주류 추가, 업종 전환, 조리 방식 변경 등 영업 형태 변경 가능성을 확인합니다.",
        "primarySlots": ["business.currentType", "business.targetChange", "business.liquorSales", "location.roadOrLotAddress"],
        "requiredNow": ["current_business_type", "target_change", "liquor_sales_if_relevant", "detailed_address"],
        "decisionModules": ["food_business_route", "building_use", "same_place_history", "documents", "departments"],
        "nextStage": "change_impact_check",
    },
    "document_readiness_check": {
        "title": "서류 준비상태 점검",
        "description": "위생교육, 건강진단결과서, 임대차계약서, 영업신고증, 사업자등록 등 준비 상태를 점검합니다.",
        "primarySlots": ["business.requestedBusinessType", "documents", "timeline.openingDate"],
        "requiredNow": ["target_permit_or_business_type"],
        "decisionModules": ["documents", "submission_order", "progress_status"],
        "nextStage": "document_checklist",
    },
    "building_use_check": {
        "title": "건축물 용도/위반건축물 확인",
        "description": "주소 기준 건축물대장 용도, 층별 용도, 위반건축물 여부를 확인합니다.",
        "primarySlots": ["location.roadOrLotAddress", "location.floorNo", "location.unitNo", "business.requestedBusinessType"],
        "requiredNow": ["detailed_address", "business_type_if_known"],
        "decisionModules": ["building_use", "violation_building"],
        "nextStage": "building_ledger_api",
    },
    "takeover_history_check": {
        "title": "기존 업소 인수/동일 장소 이력 확인",
        "description": "같은 장소에 기존 업소가 있었는지, 동일 업종 행정처분 이력이 있는지 확인합니다.",
        "primarySlots": ["location.roadOrLotAddress", "business.requestedBusinessType", "business.takeoverOrExistingBusiness"],
        "requiredNow": ["detailed_address", "target_business_type"],
        "decisionModules": ["same_place_history", "administrative_disposition"],
        "nextStage": "same_place_lookup",
    },
    "unknown": {
        "title": "목적 확인 필요",
        "description": "사용자의 인허가 목적을 먼저 분류해야 합니다.",
        "primarySlots": ["intent"],
        "requiredNow": ["service_goal"],
        "decisionModules": ["intent_classification"],
        "nextStage": "intent_clarification",
    },
}


INTENT_ALIASES: dict[str, str] = {
    "food_business_precheck": "food_business_precheck",
    "signboard_permit_check": "signboard_permit_check",
    "outdoor_space_permit_check": "outdoor_space_permit_check",
    "business_change_check": "business_change_check",
    "document_readiness_check": "document_readiness_check",
    "building_use_check": "building_use_check",
    "takeover_history_check": "takeover_history_check",
}


def normalize_intent(intent: str | None) -> str:
    return INTENT_ALIASES.get(intent or "", "unknown")


def get_scenario(intent: str | None) -> dict[str, Any]:
    scenario_id = normalize_intent(intent)
    scenario = SCENARIOS.get(scenario_id) or SCENARIOS["unknown"]
    return {"id": scenario_id, **scenario}


def build_scenario_plan(slots: dict[str, Any]) -> dict[str, Any]:
    scenario = get_scenario(slots.get("intent"))
    return {
        "selectedScenario": scenario,
        "coverageModel": {
            "strategy": "intent -> scenario -> slot requirements -> decision modules",
            "why": "시나리오를 코드 if문으로 늘리는 대신 레지스트리에 등록해 확장합니다.",
            "addNewScenarioBy": [
                "intent id 추가",
                "필수 슬롯 정의",
                "decision module 연결",
                "질문 템플릿/근거 카드 연결",
            ],
        },
    }
