from __future__ import annotations

import re
from typing import Any

from slot_contract import (
    ADDRESS_QUALITY,
    ALLOWED_BUSINESS_TYPES,
    DOCUMENT_STATE,
    SCHEMA_VERSION,
    TRI_STATE,
    build_slot_filler_prompt,
)
from gms_client import gms_chat_json
from slot_policy import derive_candidate_business_types, derive_candidate_routes, derive_missing_candidate_ids


PYEONG_TO_M2 = 3.305785

BUSINESS_TYPES = {
    "general_restaurant": "일반음식점영업",
    "cafe": "휴게음식점영업",
    "bakery": "제과점영업",
}

TRI_TO_BOOL = {"yes": True, "no": False, "unknown": None}

CONCEPT_ALIASES = {
    "cafe": [
        "카페",
        "커피",
        "커피숍",
        "커피샵",
        "커피전문점",
        "coffee",
        "coffee shop",
        "coffeeshop",
        "디저트카페",
        "디저트가게",
        "음료",
        "브런치카페",
        "테이크아웃커피",
    ],
    "restaurant": [
        "음식점",
        "식당",
        "레스토랑",
        "분식",
        "밥집",
        "요리",
        "파스타",
        "브런치식당",
    ],
    "bakery": [
        "베이커리",
        "빵집",
        "제과",
        "제빵",
        "케이크",
        "디저트샵",
    ],
    "bar": [
        "술집",
        "주점",
        "호프",
        "펍",
        "바",
        "와인바",
    ],
}

SALES_ITEM_ALIASES = {
    "음료": ["음료", "드링크", "drink"],
    "디저트": ["디저트", "dessert"],
    "커피": ["커피", "아메리카노", "라떼", "coffee"],
    "브런치": ["브런치", "brunch"],
    "빵": ["빵", "제빵", "bread"],
    "케이크": ["케이크", "cake"],
    "와인": ["와인", "wine"],
    "맥주": ["맥주", "beer"],
    "식사": ["식사", "밥", "meal"],
}


class SlotFillerProviderUnavailable(RuntimeError):
    pass


INTENT_NAMES = {
    "food_business_precheck",
    "signboard_permit_check",
    "outdoor_space_permit_check",
    "business_change_check",
    "document_readiness_check",
    "building_use_check",
    "takeover_history_check",
    "unknown",
}


def flatten_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        result: list[Any] = []
        for item in value:
            result.extend(flatten_values(item))
        return result
    return [value]


def scalar(value: Any, default: Any = None) -> Any:
    for item in flatten_values(value):
        if item is not None and not isinstance(item, (dict, list)):
            return item
    return default


def string_or_none(value: Any) -> str | None:
    item = scalar(value)
    if item is None:
        return None
    text = str(item).strip()
    return text or None


def enum_value(value: Any, allowed: list[str] | set[str], default: str) -> str:
    allowed_set = set(allowed)
    for item in flatten_values(value):
        if item is True:
            candidate = "yes"
        elif item is False:
            candidate = "no"
        else:
            candidate = str(item).strip() if item is not None and not isinstance(item, dict) else None
        if candidate in allowed_set:
            return candidate
    return default


def nullable_enum(value: Any, allowed: list[str] | set[str]) -> str | None:
    allowed_set = set(allowed)
    for item in flatten_values(value):
        if item is None or isinstance(item, dict):
            continue
        candidate = str(item).strip()
        if candidate in allowed_set:
            return candidate
    return None


def string_list(value: Any) -> list[str]:
    result: list[str] = []
    for item in flatten_values(value):
        if item is None or isinstance(item, dict):
            continue
        for part in re.split(r"\s*(?:,|/|·|ㆍ|，|、|및)\s*", str(item).strip()):
            text = part.strip()
            if text and text not in result:
                result.append(text)
    return result


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def number_or_none(value: Any) -> float | None:
    item = scalar(value)
    if item is None or item == "":
        return None
    try:
        return float(item)
    except (TypeError, ValueError):
        return None


def int_or_none(value: Any) -> int | None:
    number = number_or_none(value)
    return int(number) if number is not None else None


def normalize_gms_contract(contract: dict[str, Any]) -> dict[str, Any]:
    contract.setdefault("schemaVersion", SCHEMA_VERSION)
    intent = contract.setdefault("intent", {})
    intent["name"] = enum_value(intent.get("name"), INTENT_NAMES, "unknown")
    try:
        intent["confidence"] = max(0.0, min(float(scalar(intent.get("confidence"), 0.0)), 1.0))
    except (TypeError, ValueError):
        intent["confidence"] = 0.0

    slots = contract.setdefault("slots", {})
    location = slots.setdefault("location", {})
    location["rawText"] = string_or_none(location.get("rawText"))
    location["regionHint"] = string_or_none(location.get("regionHint"))
    location["district"] = string_or_none(location.get("district"))
    location["neighborhood"] = string_or_none(location.get("neighborhood"))
    location["addressQuality"] = enum_value(location.get("addressQuality"), ADDRESS_QUALITY, "missing")
    location["roadOrLotAddress"] = string_or_none(location.get("roadOrLotAddress"))
    location["detailAddress"] = string_or_none(location.get("detailAddress"))
    location["floorNo"] = int_or_none(location.get("floorNo"))
    location["unitNo"] = string_or_none(location.get("unitNo"))

    business = slots.setdefault("business", {})
    business["concept"] = enum_value(business.get("concept"), {"cafe", "restaurant", "bakery", "bar", "unknown"}, "unknown")
    business["requestedBusinessType"] = nullable_enum(business.get("requestedBusinessType"), ALLOWED_BUSINESS_TYPES)
    business["candidateBusinessTypes"] = [
        item for item in string_list(business.get("candidateBusinessTypes")) if item in ALLOWED_BUSINESS_TYPES
    ]
    business["salesItems"] = string_list(business.get("salesItems"))
    business["liquorSales"] = enum_value(business.get("liquorSales"), TRI_STATE, "unknown")
    try:
        business["liquorConfidence"] = max(0.0, min(float(scalar(business.get("liquorConfidence"), 0.0)), 1.0))
    except (TypeError, ValueError):
        business["liquorConfidence"] = 0.0
    business["takeoverOrExistingBusiness"] = enum_value(business.get("takeoverOrExistingBusiness"), TRI_STATE, "unknown")

    space = slots.setdefault("space", {})
    space["areaM2"] = number_or_none(space.get("areaM2"))
    space["areaPyeong"] = number_or_none(space.get("areaPyeong"))
    space["areaSourceText"] = string_or_none(space.get("areaSourceText"))
    space["isBasement"] = enum_value(space.get("isBasement"), TRI_STATE, "unknown")
    space["isSecondFloorOrHigher"] = enum_value(space.get("isSecondFloorOrHigher"), TRI_STATE, "unknown")

    facility = slots.setdefault("facility", {})
    facility["signboard"] = enum_value(facility.get("signboard"), TRI_STATE, "unknown")
    facility["signboardType"] = string_or_none(facility.get("signboardType"))
    facility["signboardSizeText"] = string_or_none(facility.get("signboardSizeText"))
    facility["outdoorSpace"] = enum_value(facility.get("outdoorSpace"), TRI_STATE, "unknown")
    facility["outdoorLocation"] = nullable_enum(
        facility.get("outdoorLocation"),
        {"road_or_sidewalk", "private_land", "terrace", "unknown"},
    )
    facility["outdoorAreaText"] = string_or_none(facility.get("outdoorAreaText"))
    facility["outdoorTableCount"] = int_or_none(facility.get("outdoorTableCount"))
    facility["delivery"] = enum_value(facility.get("delivery"), TRI_STATE, "unknown")
    facility["cookingFire"] = enum_value(facility.get("cookingFire"), TRI_STATE, "unknown")
    facility["lpgUse"] = enum_value(facility.get("lpgUse"), TRI_STATE, "unknown")
    facility["seating"] = enum_value(facility.get("seating"), TRI_STATE, "unknown")
    facility["takeoutOnly"] = enum_value(facility.get("takeoutOnly"), TRI_STATE, "unknown")

    rights = slots.setdefault("propertyRights", {})
    rights["leaseOrOwnershipStatus"] = enum_value(
        rights.get("leaseOrOwnershipStatus"),
        {"owner", "tenant", "sublease", "before_contract", "unknown"},
        "unknown",
    )
    rights["ownerManagerRelationshipKnown"] = enum_value(rights.get("ownerManagerRelationshipKnown"), TRI_STATE, "unknown")
    rights["managerConsentKnown"] = enum_value(rights.get("managerConsentKnown"), TRI_STATE, "unknown")

    documents = slots.setdefault("documents", {})
    for key in [
        "leaseContract",
        "hygieneTraining",
        "healthCertificate",
        "fireCertificate",
        "businessPermitReport",
        "businessRegistration",
    ]:
        documents[key] = enum_value(documents.get(key), DOCUMENT_STATE, "unknown")

    timeline = slots.setdefault("timeline", {})
    timeline["openingDate"] = string_or_none(timeline.get("openingDate"))
    timeline["openingDateText"] = string_or_none(timeline.get("openingDateText"))

    evidence = []
    for item in contract.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence.append(
            {
                "slot": string_or_none(item.get("slot")) or "",
                "text": string_or_none(item.get("text")) or "",
                "interpretation": string_or_none(item.get("interpretation")) or "",
            }
        )
    contract["evidence"] = evidence
    return contract


def deterministic_text_overrides(text: str) -> dict[str, Any]:
    cleaned = normalize_space(text)
    compacted = compact(cleaned)
    result: dict[str, Any] = {
        "location": {},
        "business": {},
        "space": {},
        "facility": {},
        "propertyRights": {},
    }

    road_match = re.search(
        r"((?:서울(?:특별시|시)?\s*)?[가-힣]+구\s+[가-힣0-9]+(?:대로|로|길)\s*\d+(?:-\d+)?)"
        r"(?:\s*,?\s*((?:지하\s*)?\d+\s*층))?"
        r"(?:\s*,?\s*([A-Za-z]?\d{1,5}\s*호))?",
        cleaned,
    )
    lot_match = None if road_match else re.search(
        r"((?:서울(?:특별시|시)?\s*)?[가-힣]+구\s+[가-힣0-9]+동\s*\d+(?:-\d+)?)"
        r"(?:\s*,?\s*((?:지하\s*)?\d+\s*층))?"
        r"(?:\s*,?\s*([A-Za-z]?\d{1,5}\s*호))?",
        cleaned,
    )
    address_match = road_match or lot_match
    if address_match:
        base = normalize_space(address_match.group(1))
        floor_text = normalize_space(address_match.group(2) or "")
        unit_text = normalize_space(address_match.group(3) or "")
        if base.startswith("서울시 "):
            base = "서울특별시 " + base.removeprefix("서울시 ")
        elif not base.startswith("서울"):
            base = "서울특별시 " + base
        district = re.search(r"([가-힣]+구)", base)
        neighborhood = re.search(r"([가-힣0-9]+동)", base)
        floor_no = None
        if floor_text:
            floor_num = re.search(r"(\d+)", floor_text)
            if floor_num:
                floor_no = int(floor_num.group(1)) * (-1 if "지하" in floor_text else 1)
        detail = normalize_space(" ".join(part for part in [floor_text, unit_text] if part))
        result["location"] = {
            "rawText": normalize_space(" ".join(part for part in [base, detail] if part)),
            "regionHint": " ".join(part for part in [district.group(1) if district else "", neighborhood.group(1) if neighborhood else ""] if part) or None,
            "district": district.group(1) if district else None,
            "neighborhood": neighborhood.group(1) if neighborhood else None,
            "addressQuality": "full",
            "roadOrLotAddress": base,
            "detailAddress": detail or None,
            "floorNo": floor_no,
            "unitNo": unit_text or None,
        }
    else:
        district = re.search(r"([가-힣]+구)", cleaned)
        neighborhood = re.search(r"([가-힣0-9]+동)", cleaned)
        if district or neighborhood:
            hint = " ".join(part for part in [district.group(1) if district else "", neighborhood.group(1) if neighborhood else ""] if part)
            result["location"] = {
                "rawText": hint,
                "regionHint": hint,
                "district": district.group(1) if district else None,
                "neighborhood": neighborhood.group(1) if neighborhood else None,
                "addressQuality": "partial",
            }

    pyeong = re.search(r"(\d+(?:\.\d+)?)\s*(?:평|py|pyeong)", cleaned, re.IGNORECASE)
    square_meter = re.search(r"(\d+(?:\.\d+)?)\s*(?:㎡|m2|m²|제곱미터|평방미터)", cleaned, re.IGNORECASE)
    if pyeong:
        area_pyeong = float(pyeong.group(1))
        result["space"].update(
            {
                "areaPyeong": area_pyeong,
                "areaM2": round(area_pyeong * PYEONG_TO_M2, 3),
                "areaSourceText": pyeong.group(0),
            }
        )
    elif square_meter:
        area_m2 = float(square_meter.group(1))
        result["space"].update(
            {
                "areaM2": area_m2,
                "areaPyeong": round(area_m2 / PYEONG_TO_M2, 2),
                "areaSourceText": square_meter.group(0),
            }
        )

    if re.search(r"지하\s*\d*\s*층", cleaned):
        result["space"]["isBasement"] = "yes"
    elif re.search(r"\d+\s*층", cleaned):
        result["space"]["isBasement"] = "no"
    floor_number = re.search(r"(?<!지하\s)(\d+)\s*층", cleaned)
    if floor_number:
        result["space"]["isSecondFloorOrHigher"] = "yes" if int(floor_number.group(1)) >= 2 else "no"

    if any(token in compacted for token in ["카페", "커피숍", "커피샵", "커피", "디저트", "음료"]):
        result["business"]["concept"] = "cafe"
    elif any(token in compacted for token in ["음식점", "식당", "레스토랑", "분식", "고깃집", "고기집", "삼겹살"]):
        result["business"]["concept"] = "restaurant"
    elif any(token in compacted for token in ["베이커리", "빵집", "제과"]):
        result["business"]["concept"] = "bakery"
    elif any(token in compacted for token in ["술집", "주점", "펍", "바"]):
        result["business"]["concept"] = "bar"

    sales_items = []
    for label, tokens in [
        ("음료", ["음료", "drink"]),
        ("디저트", ["디저트", "dessert"]),
        ("커피", ["커피", "아메리카노", "라떼"]),
        ("빵", ["빵", "베이커리"]),
        ("식사", ["식사", "식당", "음식"]),
        ("맥주", ["맥주"]),
        ("와인", ["와인"]),
    ]:
        if any(token.lower() in cleaned.lower() for token in tokens):
            sales_items.append(label)
    if sales_items:
        result["business"]["salesItems"] = sales_items

    liquor_negative = re.search(r"(주류|술|맥주|와인|소주)[^.\n]*(안\s*팔|팔지\s*않|판매\s*안|판매하지\s*않|미판매|없)", cleaned)
    liquor_positive = re.search(r"(주류|술|맥주|와인|소주|하이볼|칵테일)\s*(판매|팔|취급)", cleaned)
    if liquor_negative:
        result["business"]["liquorSales"] = "no"
        result["business"]["liquorConfidence"] = 0.95
    elif liquor_positive:
        result["business"]["liquorSales"] = "yes"
        result["business"]["liquorConfidence"] = 0.9

    if "간판" in cleaned or "옥외광고" in cleaned:
        result["facility"]["signboard"] = "yes"
        for signboard_type in ["벽면간판", "돌출간판", "입간판", "현수막", "전광판"]:
            if signboard_type in cleaned:
                result["facility"]["signboardType"] = signboard_type
                break
        size = re.search(r"가로\s*\d+(?:\.\d+)?\s*m\s*세로\s*\d+(?:\.\d+)?\s*m", cleaned, re.IGNORECASE)
        if size:
            result["facility"]["signboardSizeText"] = size.group(0)

    if any(token in compacted for token in ["외부테이블", "외부좌석", "테라스", "가게앞테이블", "도로점용"]):
        result["facility"]["outdoorSpace"] = "yes"
    if any(token in compacted for token in ["외부공간없", "테라스없", "외부좌석없"]):
        result["facility"]["outdoorSpace"] = "no"

    lpg_negative = re.search(r"(LPG|LP가스|액화석유가스|가스|화구|숯불)[^.\n]*(안\s*쓰|쓰지\s*않|사용\s*안|사용하지\s*않|없|미사용)", cleaned, re.IGNORECASE)
    lpg_positive = re.search(r"(LPG|LP\s*가스|액화석유가스|가스\s*화구|가스버너|가스레인지|가스렌지|화구|숯불)", cleaned, re.IGNORECASE)
    if lpg_negative:
        result["facility"]["lpgUse"] = "no"
    elif lpg_positive:
        result["facility"]["lpgUse"] = "yes"
        result["facility"]["cookingFire"] = "yes"

    if re.search(r"(건물주|소유자|관리인).{0,10}(동의|승낙).{0,10}(받|완료|있)", cleaned):
        result["propertyRights"]["managerConsentKnown"] = "yes"
        result["propertyRights"]["ownerManagerRelationshipKnown"] = "yes"

    return result


def apply_deterministic_overrides(contract: dict[str, Any], user_text: str) -> dict[str, Any]:
    overrides = deterministic_text_overrides(user_text)
    slots = contract.setdefault("slots", {})

    location_override = overrides.get("location") or {}
    if location_override.get("addressQuality") == "full" or (
        location_override.get("addressQuality") == "partial"
        and slots.get("location", {}).get("addressQuality") in {"missing", "region_only"}
    ):
        slots.setdefault("location", {}).update({key: value for key, value in location_override.items() if value is not None})

    business = slots.setdefault("business", {})
    for key in ["concept", "liquorSales", "liquorConfidence"]:
        if key in overrides.get("business", {}):
            business[key] = overrides["business"][key]
    if overrides.get("business", {}).get("salesItems"):
        business["salesItems"] = unique_strings([*(business.get("salesItems") or []), *overrides["business"]["salesItems"]])

    space = slots.setdefault("space", {})
    for key, value in (overrides.get("space") or {}).items():
        if value is not None:
            space[key] = value

    facility = slots.setdefault("facility", {})
    for key, value in (overrides.get("facility") or {}).items():
        if value is not None:
            facility[key] = value

    rights = slots.setdefault("propertyRights", {})
    for key, value in (overrides.get("propertyRights") or {}).items():
        if value is not None:
            rights[key] = value

    return normalize_gms_contract(contract)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def contains_alias(text: str, aliases: list[str]) -> bool:
    dense = compact(text).lower()
    lowered = str(text or "").lower()
    return any(compact(alias).lower() in dense or alias.lower() in lowered for alias in aliases)


def tri_state_from_keywords(text: str, positive: list[str], negative: list[str]) -> str:
    dense = compact(text)
    if any(token in dense for token in negative):
        return "no"
    if any(token in dense for token in positive):
        return "yes"
    return "unknown"


def classify_intent(text: str) -> dict[str, Any]:
    dense = compact(text)
    signboard = any(token in dense for token in ["간판", "옥외광고", "현수막", "돌출간판", "입간판", "벽면간판"])
    outdoor = any(token in dense for token in ["외부좌석", "외부테이블", "가게앞", "테라스", "야장", "도로점용", "노상"])
    opening_action = any(token in dense for token in ["창업", "열고", "오픈", "개업", "새로"])
    food_opening = any(
        token in dense
        for token in [
            "카페",
            "커피숍",
            "커피샵",
            "음식점",
            "식당",
            "베이커리",
            "휴게음식점",
            "일반음식점",
            "제과점",
        ]
    )
    document = any(token in dense for token in ["서류", "보건증", "위생교육", "영업신고증", "사업자등록"])
    document_focus = document and any(token in dense for token in ["서류", "준비", "보건증", "위생교육", "영업신고증", "사업자등록", "어디까지"])
    change = any(token in dense for token in ["변경", "추가", "전환", "업종변경", "주류추가"])
    liquor_mentioned = any(token in dense for token in ["주류", "술", "맥주", "와인", "소주", "하이볼", "칵테일"])
    building_use = any(token in dense for token in ["건축물대장", "건축물용도", "건물용도", "위반건축물", "용도확인"])
    takeover_history = any(token in dense for token in ["인수", "양도양수", "기존업소", "기존가게", "행정처분", "같은장소"])

    signboard_only = signboard and not outdoor and ("간판만" in dense or not opening_action)
    outdoor_only = outdoor and not signboard and (
        not opening_action or any(token in dense for token in ["테이블만", "도로점용만", "외부공간만"])
    )
    if signboard_only:
        return {"name": "signboard_permit_check", "confidence": 0.9}
    if outdoor_only:
        return {"name": "outdoor_space_permit_check", "confidence": 0.86}
    if takeover_history and any(token in dense for token in ["행정처분", "같은장소", "기존업소", "기존가게"]):
        return {"name": "takeover_history_check", "confidence": 0.88}
    if building_use and not opening_action:
        return {"name": "building_use_check", "confidence": 0.88}
    if takeover_history and not food_opening:
        return {"name": "takeover_history_check", "confidence": 0.82}
    if document_focus and not signboard and not outdoor and not building_use and not takeover_history:
        return {"name": "document_readiness_check", "confidence": 0.84}
    if change and (signboard or outdoor or liquor_mentioned):
        return {"name": "business_change_check", "confidence": 0.78}
    if document and not food_opening:
        return {"name": "document_readiness_check", "confidence": 0.72}
    if food_opening:
        return {"name": "food_business_precheck", "confidence": 0.95}
    return {"name": "unknown", "confidence": 0.3}


def split_lookup_address(raw: str) -> tuple[str, str]:
    lookup = normalize_space(raw)
    lookup = re.sub(r"\s*,\s*(?:지하\s*)?\d+\s*층.*$", "", lookup)
    lookup = re.sub(r"\s+(?:지하\s*)?\d+\s*층.*$", "", lookup)
    lookup = re.sub(r"\s+[A-Za-z]?\d{1,5}\s*호.*$", "", lookup)
    detail = normalize_space(raw.replace(lookup, "", 1).strip(" ,"))
    return lookup, detail


def parse_floor_and_unit(text: str) -> dict[str, Any]:
    basement = re.search(r"(?:지하|地下|b|B)\s*([0-9]+)\s*층?", text)
    ground = re.search(r"(?:지상\s*)?([0-9]+)\s*층", text)
    unit = re.search(r"([A-Za-z]?\d{1,5})\s*호", text)
    if basement:
        floor_no = -int(basement.group(1))
    elif ground:
        floor_no = int(ground.group(1))
    else:
        floor_no = None
    return {
        "floorNo": floor_no,
        "unitNo": f"{unit.group(1)}호" if unit else None,
        "isBasement": "yes" if floor_no is not None and floor_no < 0 else "no" if floor_no is not None else "unknown",
        "isSecondFloorOrHigher": "yes" if floor_no is not None and floor_no >= 2 else "no" if floor_no is not None else "unknown",
    }


def extract_location(text: str) -> dict[str, Any]:
    cleaned = normalize_space(text)
    detail_pattern = r"(?:\s*,?\s*(?:지하\s*)?\d+\s*층)?(?:\s*,?\s*[A-Za-z]?\d{1,5}\s*호)?"
    road_pattern = (
        r"((?:서울(?:특별시|시)?\s*)?[가-힣]+구\s+"
        r"[가-힣0-9]+(?:대로|로|길)\s*\d+(?:-\d+)?"
        rf"{detail_pattern})"
    )
    lot_pattern = (
        r"((?:서울(?:특별시|시)?\s*)?[가-힣]+구\s+"
        r"[가-힣0-9]+동\s*\d+(?:-\d+)?"
        rf"{detail_pattern})"
    )
    match = re.search(road_pattern, cleaned) or re.search(lot_pattern, cleaned)
    if match:
        raw = normalize_space(match.group(1).strip(" ,."))
        lookup, detail = split_lookup_address(raw)
        district = re.search(r"([가-힣]+구)", raw)
        neighborhood = re.search(r"([가-힣0-9]+동)", raw)
        parsed = parse_floor_and_unit(raw)
        address = lookup if lookup.startswith("서울") else f"서울특별시 {lookup}"
        return {
            "rawText": raw,
            "regionHint": normalize_space(" ".join(part for part in [district.group(1) if district else "", neighborhood.group(1) if neighborhood else ""] if part)) or None,
            "district": district.group(1) if district else None,
            "neighborhood": neighborhood.group(1) if neighborhood else None,
            "addressQuality": "full",
            "roadOrLotAddress": normalize_space(address),
            "detailAddress": detail or None,
            "floorNo": parsed["floorNo"],
            "unitNo": parsed["unitNo"],
        }

    district = re.search(r"([가-힣]+구)", cleaned)
    neighborhood = re.search(r"([가-힣0-9]+동)", cleaned)
    region_hint = normalize_space(" ".join(part for part in [district.group(1) if district else "", neighborhood.group(1) if neighborhood else ""] if part))
    quality = "partial" if region_hint else "missing"
    return {
        "rawText": region_hint or None,
        "regionHint": region_hint or None,
        "district": district.group(1) if district else None,
        "neighborhood": neighborhood.group(1) if neighborhood else None,
        "addressQuality": quality,
        "roadOrLotAddress": None,
        "detailAddress": None,
        "floorNo": None,
        "unitNo": None,
    }


def extract_area(text: str) -> dict[str, Any]:
    pyeong = re.search(r"(\d+(?:\.\d+)?)\s*(?:평|py|pyeong)", text, re.IGNORECASE)
    if pyeong:
        area_pyeong = float(pyeong.group(1))
        return {
            "areaM2": round(area_pyeong * PYEONG_TO_M2, 2),
            "areaPyeong": area_pyeong,
            "areaSourceText": pyeong.group(0),
        }
    square_meter = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|㎡|제곱미터|제곱|평방미터)", text, re.IGNORECASE)
    if square_meter:
        area_m2 = float(square_meter.group(1))
        return {
            "areaM2": area_m2,
            "areaPyeong": round(area_m2 / PYEONG_TO_M2, 2),
            "areaSourceText": square_meter.group(0),
        }
    return {"areaM2": None, "areaPyeong": None, "areaSourceText": None}


def extract_business(text: str) -> dict[str, Any]:
    dense = compact(text)
    requested = None
    if "일반음식점" in dense:
        requested = BUSINESS_TYPES["general_restaurant"]
    elif "휴게음식점" in dense:
        requested = BUSINESS_TYPES["cafe"]
    elif "제과점" in dense:
        requested = BUSINESS_TYPES["bakery"]

    concept = "unknown"
    for concept_name, aliases in CONCEPT_ALIASES.items():
        if contains_alias(text, aliases):
            concept = concept_name
            break

    if requested:
        candidates = [requested]
    elif concept == "bakery":
        candidates = [BUSINESS_TYPES["bakery"]]
    elif concept in {"restaurant", "bar"}:
        candidates = [BUSINESS_TYPES["general_restaurant"]]
    elif concept == "cafe":
        candidates = [BUSINESS_TYPES["cafe"], BUSINESS_TYPES["general_restaurant"]]
    else:
        candidates = [BUSINESS_TYPES["cafe"], BUSINESS_TYPES["general_restaurant"], BUSINESS_TYPES["bakery"]]

    liquor = tri_state_from_keywords(
        text,
        positive=["주류", "술", "맥주", "와인", "소주", "칵테일", "하이볼", "위스키", "막걸리"],
        negative=[
            "주류안",
            "주류는안",
            "주류안팔",
            "주류팔지않",
            "주류는팔지않",
            "주류판매안",
            "주류판매없",
            "주류판매하지않",
            "주류취급안",
            "주류취급하지않",
            "술안",
            "술은안",
            "술안팔",
            "술팔지않",
            "술은팔지않",
            "술판매안",
            "술판매하지않",
            "술취급안",
            "술취급하지않",
            "주류없",
            "술없",
            "무알콜",
            "안팔아요",
            "안팔",
            "팔지않",
            "판매안",
            "판매하지않",
            "취급안",
            "취급하지않",
        ],
    )
    sales_items = []
    for canonical_item, aliases in SALES_ITEM_ALIASES.items():
        if contains_alias(text, aliases):
            sales_items.append(canonical_item)
    if liquor == "unknown" and concept == "cafe" and any(item in sales_items for item in ["음료", "디저트", "커피", "빵", "케이크"]):
        liquor = "no"
        liquor_confidence = 0.72
    else:
        liquor_confidence = 0.95 if liquor != "unknown" else 0.0
    if liquor == "yes" and BUSINESS_TYPES["general_restaurant"] not in candidates:
        candidates.append(BUSINESS_TYPES["general_restaurant"])

    takeover = tri_state_from_keywords(
        text,
        positive=["인수", "양도양수", "기존가게", "기존 업소", "전에 하던", "같은 장소"],
        negative=["신규", "새로", "처음"],
    )
    return {
        "concept": concept,
        "requestedBusinessType": requested,
        "candidateBusinessTypes": candidates,
        "salesItems": sales_items,
        "liquorSales": liquor,
        "liquorConfidence": liquor_confidence,
        "takeoverOrExistingBusiness": takeover,
    }


def neutral_business_slot() -> dict[str, Any]:
    return {
        "concept": "unknown",
        "requestedBusinessType": None,
        "candidateBusinessTypes": [],
        "salesItems": [],
        "liquorSales": "unknown",
        "liquorConfidence": 0.0,
        "takeoverOrExistingBusiness": "unknown",
    }


def extract_facility(text: str) -> dict[str, str]:
    dense = compact(text)
    signboard_type = None
    for token in ["벽면간판", "돌출간판", "입간판", "현수막", "전면간판", "전광판"]:
        if token in dense:
            signboard_type = token
            break
    size_match = re.search(
        r"(?:가로\s*)?\d+(?:\.\d+)?\s*(?:m|미터|㎡|제곱미터)\s*(?:세로\s*)?\d*(?:\.\d+)?\s*(?:m|미터|㎡|제곱미터)?",
        text,
        re.IGNORECASE,
    )
    outdoor_location = None
    if any(token in dense for token in ["보도", "도로", "인도", "차도", "도로점용"]):
        outdoor_location = "road_or_sidewalk"
    elif any(token in dense for token in ["사유지", "건물앞마당", "대지안", "건물부지"]):
        outdoor_location = "private_land"
    elif any(token in dense for token in ["테라스", "야장"]):
        outdoor_location = "terrace"
    table_match = re.search(r"(?:테이블|좌석)\s*(\d+)\s*개", text)
    if not table_match:
        table_match = re.search(r"(\d+)\s*개\s*(?:테이블|좌석)", text)
    outdoor_area_match = re.search(
        r"(?:외부|보도|도로|테라스|야장|가게\s*앞)[^.\n]{0,20}?(\d+(?:\.\d+)?\s*(?:㎡|m2|제곱미터|평))",
        text,
        re.IGNORECASE,
    )
    return {
        "signboard": tri_state_from_keywords(text, ["간판", "옥외광고"], ["간판안", "간판없"]),
        "signboardType": signboard_type,
        "signboardSizeText": size_match.group(0) if size_match and signboard_type else None,
        "outdoorSpace": tri_state_from_keywords(
            text,
            ["외부좌석", "외부 좌석", "테라스", "야장", "노상", "도로점용", "가게앞", "가게 앞", "앞에테이블", "앞에 테이블", "밖에 테이블"],
            ["외부좌석안", "테라스없"],
        ),
        "outdoorLocation": outdoor_location or "unknown",
        "outdoorAreaText": outdoor_area_match.group(1) if outdoor_area_match and outdoor_location else None,
        "outdoorTableCount": int(table_match.group(1)) if table_match else None,
        "delivery": tri_state_from_keywords(text, ["배달", "포장", "테이크아웃"], ["배달안", "포장안"]),
        "cookingFire": tri_state_from_keywords(text, ["조리", "주방", "가스", "불사용", "튀김"], ["조리안", "불사용안"]),
        "lpgUse": tri_state_from_keywords(
            text,
            ["LPG", "LP가스", "액화석유가스", "가스화구", "가스 화구", "가스버너", "가스레인지", "가스렌지", "화구", "숯불"],
            ["LPG안", "가스안", "가스사용안", "가스사용하지않", "가스없", "화구없"],
        ),
        "seating": tri_state_from_keywords(text, ["좌석", "홀", "테이블"], ["좌석없", "테이크아웃만", "포장만"]),
        "takeoutOnly": tri_state_from_keywords(text, ["테이크아웃만", "포장만"], ["좌석", "홀", "테이블"]),
    }


def extract_property_rights(text: str) -> dict[str, str]:
    dense = compact(text)
    if "자가" in dense or "소유" in dense:
        lease_status = "owner"
    elif "전대" in dense or "전차" in dense:
        lease_status = "sublease"
    elif "계약전" in dense or "계약예정" in dense:
        lease_status = "before_contract"
    elif "임대" in dense or "월세" in dense or "계약" in dense:
        lease_status = "tenant"
    else:
        lease_status = "unknown"
    owner_manager = tri_state_from_keywords(text, ["소유자", "관리인", "건물주"], [])
    manager_consent = tri_state_from_keywords(text, ["동의", "허락", "승낙"], ["동의안", "허락안", "승낙안"])
    return {
        "leaseOrOwnershipStatus": lease_status,
        "ownerManagerRelationshipKnown": owner_manager,
        "managerConsentKnown": manager_consent,
    }


def doc_state(text: str, tokens: list[str]) -> str:
    dense = compact(text)
    negative_markers = ["없", "전", "예정", "아직", "미발급", "안받", "안들", "못받", "못들"]
    positive_markers = ["있", "완료", "받", "발급", "수료", "준비됨", "준비완료", "가지고"]
    for token in tokens:
        if token not in dense:
            continue
        index = dense.find(token)
        window = dense[max(0, index - 8) : index + len(token) + 12]
        if any(marker in window for marker in negative_markers):
            return "not_prepared"
        if any(marker in window for marker in positive_markers):
            return "prepared"
    return "unknown"


def extract_documents(text: str) -> dict[str, str]:
    return {
        "leaseContract": doc_state(text, ["임대차", "계약서"]),
        "hygieneTraining": doc_state(text, ["위생교육", "교육수료"]),
        "healthCertificate": doc_state(text, ["보건증", "건강진단결과서"]),
        "fireCertificate": doc_state(text, ["소방필증", "소방완비", "안전시설등완비"]),
        "businessPermitReport": doc_state(text, ["영업신고증", "영업신고"]),
        "businessRegistration": doc_state(text, ["사업자등록"]),
    }


def extract_timeline(text: str) -> dict[str, str | None]:
    match = re.search(r"(\d{4})[.-](\d{1,2})[.-](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return {"openingDate": f"{int(year):04d}-{int(month):02d}-{int(day):02d}", "openingDateText": match.group(0)}
    rough = re.search(r"(다음 달|이번 달|내년|올해|[0-9]+월\s*[0-9]*일?)", text)
    return {"openingDate": None, "openingDateText": rough.group(0) if rough else None}


def build_evidence(text: str, contract: dict[str, Any]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    slots = contract["slots"]
    location = slots["location"]
    if location["rawText"]:
        evidence.append({"slot": "location.regionHint", "text": location["rawText"], "interpretation": "사용자가 말한 위치 정보"})
    space = slots["space"]
    if space["areaSourceText"]:
        evidence.append({"slot": "space.area", "text": space["areaSourceText"], "interpretation": "영업장 면적"})
    for item in slots["business"]["salesItems"]:
        evidence.append({"slot": "business.salesItems", "text": item, "interpretation": "판매 품목"})
    if slots["facility"]["signboard"] == "yes":
        evidence.append({"slot": "facility.signboard", "text": "간판", "interpretation": "간판 설치 예정"})
    if slots["facility"]["outdoorSpace"] == "yes":
        evidence.append({"slot": "facility.outdoorSpace", "text": "가게 앞/외부 테이블", "interpretation": "외부 공간 사용 예정"})
    if slots["facility"].get("lpgUse") == "yes":
        evidence.append({"slot": "facility.lpgUse", "text": "LPG/가스/화구", "interpretation": "가스 사용시설 완성검사 대상 여부 확인 필요"})
    return evidence


def build_missing_candidates(contract: dict[str, Any]) -> dict[str, list[str]]:
    return derive_missing_candidate_ids(contract["slots"])


def rule_based_slot_fill(user_text: str) -> dict[str, Any]:
    text = normalize_space(user_text)
    intent = classify_intent(text)
    location = extract_location(text)
    floor_info = parse_floor_and_unit(text)
    space = {**extract_area(text), "isBasement": floor_info["isBasement"], "isSecondFloorOrHigher": floor_info["isSecondFloorOrHigher"]}
    if intent["name"] in {"signboard_permit_check", "outdoor_space_permit_check"}:
        business = neutral_business_slot()
    else:
        business = extract_business(text)
    contract = {
        "schemaVersion": SCHEMA_VERSION,
        "intent": intent,
        "slots": {
            "location": location,
            "business": business,
            "space": space,
            "facility": extract_facility(text),
            "propertyRights": extract_property_rights(text),
            "documents": extract_documents(text),
            "timeline": extract_timeline(text),
        },
        "evidence": [],
        "missingCandidates": {},
    }
    if intent["name"] in {"food_business_precheck", "business_change_check"}:
        contract["slots"]["business"]["candidateBusinessTypes"] = derive_candidate_business_types(contract["slots"]["business"])
    contract["evidence"] = build_evidence(text, contract)
    if intent["name"] in {"food_business_precheck", "business_change_check"}:
        contract["missingCandidates"] = build_missing_candidates(contract)
    else:
        contract["missingCandidates"] = {
            "requiredForRouteScreening": [],
            "requiredForBuildingCheck": [],
            "recommendedForChecklist": [],
            "laterForProgress": [],
        }
    return contract


def gms_slot_fill(user_text: str) -> dict[str, Any]:
    prompt_payload = build_slot_filler_prompt(user_text)
    contract = gms_chat_json(
        system_prompt=prompt_payload["system"],
        user_payload=prompt_payload["user"],
        temperature=0.0,
        max_output_tokens=3600,
        timeout=60,
    )
    contract.pop("_gmsMeta", None)
    contract = apply_deterministic_overrides(normalize_gms_contract(contract), user_text)
    if contract.get("intent", {}).get("name") in {"food_business_precheck", "business_change_check"}:
        contract["slots"]["business"]["candidateBusinessTypes"] = derive_candidate_business_types(contract["slots"]["business"])
        contract["missingCandidates"] = derive_missing_candidate_ids(contract["slots"])
    else:
        contract.setdefault(
            "missingCandidates",
            {
                "requiredForRouteScreening": [],
                "requiredForBuildingCheck": [],
                "recommendedForChecklist": [],
                "laterForProgress": [],
            },
        )
    return contract


def fill_slots(user_text: str, provider: str = "rule", fallback_to_rule: bool = True) -> dict[str, Any]:
    provider = (provider or "rule").lower()
    meta = {"requestedProvider": provider, "provider": provider, "fallbackUsed": False, "fallbackReason": ""}
    if provider == "rule":
        return {"contract": rule_based_slot_fill(user_text), "meta": meta}
    if provider == "gms":
        try:
            return {"contract": gms_slot_fill(user_text), "meta": meta}
        except Exception as exc:
            if not fallback_to_rule:
                raise
            meta.update({"provider": "rule", "fallbackUsed": True, "fallbackReason": f"{type(exc).__name__}: {exc}"})
            return {"contract": rule_based_slot_fill(user_text), "meta": meta}
    raise ValueError(f"Unknown slot filler provider: {provider}")


def tri_to_bool(value: str | None) -> bool | None:
    return TRI_TO_BOOL.get(value or "unknown")


def doc_to_pipeline_state(value: str) -> str:
    if value == "prepared":
        return "prepared"
    if value == "not_prepared":
        return "not_prepared"
    return "unknown"


def contract_to_pipeline_slots(contract: dict[str, Any], original_text: str) -> dict[str, Any]:
    slots = contract["slots"]
    location = slots["location"]
    business = slots["business"]
    space = slots["space"]
    facility = slots["facility"]
    docs = slots["documents"]
    if contract["intent"]["name"] in {"food_business_precheck", "business_change_check"}:
        candidate_routes = derive_candidate_routes(business, space, facility)
    else:
        candidate_routes = []
    if candidate_routes:
        candidate_types = [route["businessType"] for route in candidate_routes]
    elif contract["intent"]["name"] in {"building_use_check", "takeover_history_check", "document_readiness_check"}:
        candidate_types = business["candidateBusinessTypes"]
    else:
        candidate_types = []
    address_full = ""
    if location["roadOrLotAddress"]:
        address_full = normalize_space(" ".join(part for part in [location["roadOrLotAddress"], location["detailAddress"]] if part))
    address_raw = location["roadOrLotAddress"] or location["regionHint"] or location["rawText"] or ""
    return {
        "intent": contract["intent"]["name"],
        "address": {
            "raw": address_raw,
            "full": address_full,
            "lookupAddress": location["roadOrLotAddress"] or "",
            "detail": location["detailAddress"] or "",
            "quality": "full" if location["addressQuality"] == "full" else "partial" if location["regionHint"] else "missing",
            "hasDistrict": bool(location["district"]),
            "hasRoadOrLotNumber": bool(location["roadOrLotAddress"]),
            "hasFloor": location["floorNo"] is not None,
            "hasUnit": bool(location["unitNo"]),
            "source": "slot_filler",
        },
        "business": {
            "rawText": original_text,
            "concept": business["concept"],
            "requestedType": business["requestedBusinessType"],
            "candidateTypes": candidate_types,
            "candidateRoutes": candidate_routes,
            "liquorSales": tri_to_bool(business["liquorSales"]),
            "confidence": "high" if contract["intent"]["confidence"] >= 0.8 else "medium",
            "salesItems": business["salesItems"],
            "takeoverOrExistingBusiness": tri_to_bool(business["takeoverOrExistingBusiness"]),
        },
        "space": {
            "areaM2": space["areaM2"],
            "areaPyeong": space["areaPyeong"],
            "source": "slot_filler" if space["areaSourceText"] else "missing",
            "confidence": "high" if space["areaM2"] is not None else "none",
            "isBasement": tri_to_bool(space["isBasement"]),
            "isSecondFloorOrHigher": tri_to_bool(space["isSecondFloorOrHigher"]),
        },
        "facility": {
            "signboard": tri_to_bool(facility["signboard"]),
            "signboardType": facility.get("signboardType"),
            "signboardSizeText": facility.get("signboardSizeText"),
            "outdoorSpace": tri_to_bool(facility["outdoorSpace"]),
            "outdoorLocation": facility.get("outdoorLocation"),
            "outdoorAreaText": facility.get("outdoorAreaText"),
            "outdoorTableCount": facility.get("outdoorTableCount"),
            "delivery": tri_to_bool(facility["delivery"]),
            "cookingFire": tri_to_bool(facility["cookingFire"]),
            "lpgUse": tri_to_bool(facility.get("lpgUse")),
            "seating": tri_to_bool(facility["seating"]),
            "takeoutOnly": tri_to_bool(facility["takeoutOnly"]),
        },
        "propertyRights": {
            **slots["propertyRights"],
        },
        "documents": {
            "leaseContract": doc_to_pipeline_state(docs["leaseContract"]),
            "hygieneTraining": doc_to_pipeline_state(docs["hygieneTraining"]),
            "healthCertificate": doc_to_pipeline_state(docs["healthCertificate"]),
            "fireCertificate": doc_to_pipeline_state(docs["fireCertificate"]),
            "businessPermitReport": doc_to_pipeline_state(docs["businessPermitReport"]),
            "businessRegistration": doc_to_pipeline_state(docs["businessRegistration"]),
            "idCard": "unknown",
        },
        "timeline": slots["timeline"],
    }
