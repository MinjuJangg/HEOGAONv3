from __future__ import annotations

from typing import Any


BUSINESS_TYPES = {
    "general_restaurant": "일반음식점영업",
    "cafe": "휴게음식점영업",
    "bakery": "제과점영업",
}

ALLOWED_BUSINESS_TYPES = set(BUSINESS_TYPES.values())

ROUTE_EVIDENCE = {
    "food_hygiene_enforcement_decree_article_21_8_a": {
        "title": "식품위생법 시행령 제21조 제8호 가목",
        "url": "https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsId=004097&lsJoLnkSeq=900232309&print=print",
        "summary": "휴게음식점영업은 다류, 아이스크림류, 패스트푸드점, 분식점 형태 등의 음식류 조리ㆍ판매 영업이며 음주행위가 허용되지 않습니다.",
    },
    "food_hygiene_enforcement_decree_article_21_8_b": {
        "title": "식품위생법 시행령 제21조 제8호 나목",
        "url": "https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsId=004097&lsJoLnkSeq=900232309&print=print",
        "summary": "일반음식점영업은 음식류를 조리ㆍ판매하고 식사와 함께 부수적으로 음주행위가 허용되는 영업입니다.",
    },
    "food_hygiene_enforcement_decree_article_21_8_f": {
        "title": "식품위생법 시행령 제21조 제8호 바목",
        "url": "https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsId=004097&lsJoLnkSeq=900232309&print=print",
        "summary": "제과점영업은 주로 빵, 떡, 과자 등을 제조ㆍ판매하는 영업이며 음주행위가 허용되지 않습니다.",
    },
}


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def normalize_liquor(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return value if value in {"yes", "no", "unknown"} else "unknown"


def route_candidate(
    business_type: str,
    score: float,
    status: str,
    reasons: list[str],
    evidence_ids: list[str],
    signals: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "businessType": business_type,
        "score": round(max(0.0, min(score, 1.0)), 2),
        "status": status,
        "reasons": reasons,
        "evidenceIds": evidence_ids,
        "signals": signals or [],
        "sourceReferences": [ROUTE_EVIDENCE[eid] for eid in evidence_ids if eid in ROUTE_EVIDENCE],
    }


def merge_route(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return incoming

    status_priority = {
        "blocked_by_liquor": 5,
        "candidate": 4,
        "llm_proposed_needs_validation": 3,
        "needs_more_info": 2,
    }
    merged = {**existing}
    merged["score"] = round(max(existing.get("score", 0), incoming.get("score", 0)), 2)
    if status_priority.get(incoming.get("status"), 0) > status_priority.get(existing.get("status"), 0):
        merged["status"] = incoming["status"]
    merged["reasons"] = unique([*(existing.get("reasons") or []), *(incoming.get("reasons") or [])])
    merged["evidenceIds"] = unique([*(existing.get("evidenceIds") or []), *(incoming.get("evidenceIds") or [])])
    merged["signals"] = unique([*(existing.get("signals") or []), *(incoming.get("signals") or [])])
    source_refs = {}
    for ref in [*(existing.get("sourceReferences") or []), *(incoming.get("sourceReferences") or [])]:
        if ref.get("title"):
            source_refs[ref["title"]] = ref
    merged["sourceReferences"] = list(source_refs.values())
    return merged


def derive_candidate_routes(
    business_slot: dict[str, Any],
    space_slot: dict[str, Any] | None = None,
    facility_slot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build evidence-backed route candidates from primitive slots.

    LLM/GMS may propose candidates, but this function is the backend resolver.
    It uses extracted facts plus legal evidence cards to score routes.
    """
    requested = business_slot.get("requestedBusinessType") or business_slot.get("requestedType")
    concept = business_slot.get("concept") or "unknown"
    liquor = normalize_liquor(business_slot.get("liquorSales"))
    sales_items = set(business_slot.get("salesItems") or [])
    proposed_candidates = [item for item in business_slot.get("candidateBusinessTypes", []) if item in ALLOWED_BUSINESS_TYPES]
    routes: list[dict[str, Any]] = []

    for proposed in proposed_candidates:
        if liquor == "yes" and proposed in {BUSINESS_TYPES["cafe"], BUSINESS_TYPES["bakery"]}:
            routes.append(
                route_candidate(
                    proposed,
                    0.2,
                    "blocked_by_liquor",
                    ["LLM/GMS가 후보로 제안했지만, 주류 판매 계획과 충돌해 제한 후보로 표시합니다."],
                    evidence_for_business_type(proposed),
                    ["llm_proposed"],
                )
            )
        else:
            routes.append(
                route_candidate(
                    proposed,
                    0.62,
                    "llm_proposed_needs_validation",
                    ["LLM/GMS가 사용자 표현을 해석해 이 영업 유형을 후보로 제안했습니다."],
                    evidence_for_business_type(proposed),
                    ["llm_proposed"],
                )
            )

    cafe_like = concept == "cafe" or bool(sales_items & {"음료", "커피", "디저트", "브런치"})
    bakery_like = concept == "bakery" or bool(sales_items & {"빵", "케이크", "과자", "떡"})
    meal_like = concept in {"restaurant", "bar"} or bool(sales_items & {"식사", "요리", "파스타", "분식"})

    if requested in ALLOWED_BUSINESS_TYPES:
        routes.append(
                route_candidate(
                    requested,
                    0.9,
                    "candidate",
                    ["사용자가 특정 영업 유형을 직접 언급했습니다."],
                    evidence_for_business_type(requested),
                    ["explicit_user_request"],
                )
            )

    if cafe_like and requested != BUSINESS_TYPES["bakery"]:
        if liquor == "yes":
            routes.append(
                route_candidate(
                    BUSINESS_TYPES["cafe"],
                    0.2,
                    "blocked_by_liquor",
                    ["카페/음료ㆍ디저트 맥락은 휴게음식점 후보지만, 주류 판매 계획이 있어 휴게음식점 경로는 제한됩니다."],
                    ["food_hygiene_enforcement_decree_article_21_8_a"],
                    ["semantic_match", "legal_conflict"],
                )
            )
        else:
            routes.append(
                route_candidate(
                    BUSINESS_TYPES["cafe"],
                    0.86 if liquor == "no" else 0.68,
                    "candidate",
                    ["카페, 음료, 디저트 맥락은 휴게음식점영업 후보와 잘 맞습니다."],
                    ["food_hygiene_enforcement_decree_article_21_8_a"],
                    ["semantic_match"],
                )
            )

    if bakery_like:
        if liquor == "yes":
            routes.append(
                route_candidate(
                    BUSINESS_TYPES["bakery"],
                    0.2,
                    "blocked_by_liquor",
                    ["빵/제과류 맥락은 제과점 후보지만, 주류 판매 계획이 있으면 제과점 경로는 제한됩니다."],
                    ["food_hygiene_enforcement_decree_article_21_8_f"],
                    ["semantic_match", "legal_conflict"],
                )
            )
        else:
            routes.append(
                route_candidate(
                    BUSINESS_TYPES["bakery"],
                    0.78,
                    "candidate",
                    ["빵, 과자, 케이크, 떡 제조ㆍ판매 맥락은 제과점영업 후보입니다."],
                    ["food_hygiene_enforcement_decree_article_21_8_f"],
                    ["semantic_match"],
                )
            )

    if meal_like or liquor == "yes" or concept == "cafe":
        reasons = []
        score = 0.55
        if liquor == "yes":
            score = 0.9
            reasons.append("주류 판매 계획이 있으면 일반음식점영업 경로를 우선 검토해야 합니다.")
        if meal_like:
            score = max(score, 0.82)
            reasons.append("음식류 조리ㆍ식사 제공 맥락은 일반음식점영업 후보입니다.")
        if concept == "cafe" and liquor != "yes":
            reasons.append("카페라도 조리ㆍ좌석ㆍ판매 방식에 따라 일반음식점영업 후보를 함께 검토합니다.")
        routes.append(
            route_candidate(
                BUSINESS_TYPES["general_restaurant"],
                score,
                "candidate",
                reasons or ["일반음식점영업 가능성을 보조 후보로 검토합니다."],
                ["food_hygiene_enforcement_decree_article_21_8_b"],
                ["semantic_match" if meal_like or liquor == "yes" else "fallback_candidate"],
            )
        )

    if not routes:
        routes.extend(
            [
                route_candidate(BUSINESS_TYPES["cafe"], 0.45, "needs_more_info", ["업종 설명이 부족해 휴게음식점 후보를 보류 상태로 둡니다."], ["food_hygiene_enforcement_decree_article_21_8_a"]),
                route_candidate(BUSINESS_TYPES["general_restaurant"], 0.45, "needs_more_info", ["업종 설명이 부족해 일반음식점 후보를 보류 상태로 둡니다."], ["food_hygiene_enforcement_decree_article_21_8_b"]),
                route_candidate(BUSINESS_TYPES["bakery"], 0.35, "needs_more_info", ["제과류 제조ㆍ판매 여부가 확인되지 않았습니다."], ["food_hygiene_enforcement_decree_article_21_8_f"]),
            ]
        )

    deduped: dict[str, dict[str, Any]] = {}
    for route in routes:
        current = deduped.get(route["businessType"])
        deduped[route["businessType"]] = merge_route(current, route)
    return sorted(deduped.values(), key=lambda item: item["score"], reverse=True)


def evidence_for_business_type(business_type: str) -> list[str]:
    if business_type == BUSINESS_TYPES["cafe"]:
        return ["food_hygiene_enforcement_decree_article_21_8_a"]
    if business_type == BUSINESS_TYPES["general_restaurant"]:
        return ["food_hygiene_enforcement_decree_article_21_8_b"]
    if business_type == BUSINESS_TYPES["bakery"]:
        return ["food_hygiene_enforcement_decree_article_21_8_f"]
    return []


def derive_candidate_business_types(business_slot: dict[str, Any]) -> list[str]:
    """Derive route candidates from primitive slots, not from LLM judgement.

    The LLM may extract concept/sales/liquor/requested type, but this policy
    decides which legal business-type routes should be evaluated.
    """
    return unique([route["businessType"] for route in derive_candidate_routes(business_slot)])


def derive_missing_candidate_ids(contract_slots: dict[str, Any]) -> dict[str, list[str]]:
    """Classify missing fields by workflow stage.

    This is deterministic product policy. The LLM can suggest missing fields,
    but the backend should compute the final buckets.
    """
    route_required: list[str] = []
    building_required: list[str] = []
    recommended: list[str] = []
    later: list[str] = []

    business = contract_slots["business"]
    location = contract_slots["location"]
    space = contract_slots["space"]
    documents = contract_slots["documents"]
    property_rights = contract_slots.get("propertyRights") or {}

    if business.get("concept") == "unknown":
        route_required.append("business_concept")
    if business.get("liquorSales") == "unknown":
        route_required.append("liquor_sales")
    if space.get("areaM2") is None:
        route_required.append("area")

    if location.get("addressQuality") != "full":
        building_required.append("detailed_address")
    if location.get("floorNo") is None and not location.get("unitNo"):
        building_required.append("floor_or_unit_if_known")

    if documents.get("leaseContract") == "unknown":
        recommended.append("lease_contract")
    if property_rights.get("ownerManagerRelationshipKnown") == "unknown":
        recommended.append("owner_or_manager_permission")
    if business.get("takeoverOrExistingBusiness") == "unknown":
        recommended.append("takeover_or_existing_business")

    for key, missing_id in [
        ("hygieneTraining", "hygiene_training"),
        ("healthCertificate", "health_certificate"),
        ("fireCertificate", "fire_certificate"),
    ]:
        if documents.get(key) == "unknown":
            later.append(missing_id)

    return {
        "requiredForRouteScreening": route_required,
        "requiredForBuildingCheck": building_required,
        "recommendedForChecklist": recommended,
        "laterForProgress": later,
    }
