from __future__ import annotations

import argparse
import json
from typing import Any


SCHEMA_VERSION = "heogaon.intake.v1"

ALLOWED_BUSINESS_TYPES = ["휴게음식점영업", "일반음식점영업", "제과점영업"]
TRI_STATE = ["yes", "no", "unknown"]
ADDRESS_QUALITY = ["missing", "region_only", "partial", "full"]
DOCUMENT_STATE = ["prepared", "not_prepared", "unknown"]


SLOT_FILLER_SYSTEM_PROMPT = """
너는 허가온의 AI slot filler다.
사용자의 자연어 창업 설명에서 인허가 사전진단에 필요한 조건만 구조화한다.

중요 원칙:
1. 법적 최종 판단을 하지 않는다. 판단은 decision engine과 graph가 한다.
2. 사용자 문장에 없는 정보는 지어내지 말고 unknown/null로 둔다.
3. 주소는 지역 힌트, API 조회용 도로명/지번 주소, 층/호수까지 포함한 사업장 전체 주소를 분리한다.
4. 주류 판매 여부는 핵심 분기 조건이므로 반드시 yes/no/unknown 중 하나로 둔다.
5. 면적은 평/㎡를 모두 인식하고, 가능하면 둘 다 채운다.
6. 사용자가 카페라고 쓰지 않아도 커피숍, 커피샵, 디저트 가게, 브런치 매장, 테이크아웃 커피 전문점처럼 의미가 같으면 concept=cafe로 정규화한다.
7. 층/지하 여부, 간판, 외부공간, 조리, 배달, 좌석, LPG/가스 화구 사용 여부를 분리한다.
8. 임대차/소유자/관리인 권한과 기존 업소 인수 여부는 모르면 unknown으로 둔다.
9. candidateBusinessTypes와 missingCandidates는 제안값이다. 최종 후보/부족정보 분류는 백엔드 정책 룰이 다시 계산한다.
10. 각 핵심 슬롯은 근거가 된 원문 조각(evidence)을 함께 남긴다.
11. 출력은 반드시 JSON 하나만 반환한다. 설명 문장을 JSON 밖에 쓰지 않는다.
""".strip()


SLOT_FILLER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schemaVersion", "intent", "slots", "evidence", "missingCandidates"],
    "properties": {
        "schemaVersion": {"type": "string", "const": SCHEMA_VERSION},
        "intent": {
            "type": "object",
            "required": ["name", "confidence"],
            "properties": {
                "name": {
                    "type": "string",
                    "enum": [
                        "food_business_precheck",
                        "signboard_permit_check",
                        "outdoor_space_permit_check",
                        "business_change_check",
                        "document_readiness_check",
                        "building_use_check",
                        "takeover_history_check",
                        "unknown",
                    ],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "additionalProperties": False,
        },
        "slots": {
            "type": "object",
            "required": ["location", "business", "space", "facility", "propertyRights", "documents", "timeline"],
            "properties": {
                "location": {
                    "type": "object",
                    "required": [
                        "rawText",
                        "regionHint",
                        "district",
                        "neighborhood",
                        "addressQuality",
                        "roadOrLotAddress",
                        "detailAddress",
                        "floorNo",
                        "unitNo",
                    ],
                    "properties": {
                        "rawText": {"type": ["string", "null"]},
                        "regionHint": {"type": ["string", "null"]},
                        "district": {"type": ["string", "null"]},
                        "neighborhood": {"type": ["string", "null"]},
                        "addressQuality": {"type": "string", "enum": ADDRESS_QUALITY},
                        "roadOrLotAddress": {"type": ["string", "null"]},
                        "detailAddress": {"type": ["string", "null"]},
                        "floorNo": {"type": ["integer", "null"]},
                        "unitNo": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                "business": {
                    "type": "object",
                    "required": [
                        "concept",
                        "requestedBusinessType",
                        "candidateBusinessTypes",
                        "salesItems",
                        "liquorSales",
                        "liquorConfidence",
                        "takeoverOrExistingBusiness",
                    ],
                    "properties": {
                        "concept": {"type": "string", "enum": ["cafe", "restaurant", "bakery", "bar", "unknown"]},
                        "requestedBusinessType": {"type": ["string", "null"], "enum": [*ALLOWED_BUSINESS_TYPES, None]},
                        "candidateBusinessTypes": {
                            "type": "array",
                            "items": {"type": "string", "enum": ALLOWED_BUSINESS_TYPES},
                        },
                        "salesItems": {"type": "array", "items": {"type": "string"}},
                        "liquorSales": {"type": "string", "enum": TRI_STATE},
                        "liquorConfidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "takeoverOrExistingBusiness": {"type": "string", "enum": TRI_STATE},
                    },
                    "additionalProperties": False,
                },
                "space": {
                    "type": "object",
                    "required": ["areaM2", "areaPyeong", "areaSourceText", "isBasement", "isSecondFloorOrHigher"],
                    "properties": {
                        "areaM2": {"type": ["number", "null"]},
                        "areaPyeong": {"type": ["number", "null"]},
                        "areaSourceText": {"type": ["string", "null"]},
                        "isBasement": {"type": "string", "enum": TRI_STATE},
                        "isSecondFloorOrHigher": {"type": "string", "enum": TRI_STATE},
                    },
                    "additionalProperties": False,
                },
                "facility": {
                    "type": "object",
                    "required": [
                        "signboard",
                        "signboardType",
                        "signboardSizeText",
                        "outdoorSpace",
                        "outdoorLocation",
                        "outdoorAreaText",
                        "outdoorTableCount",
                        "delivery",
                        "cookingFire",
                        "lpgUse",
                        "seating",
                        "takeoutOnly",
                    ],
                    "properties": {
                        "signboard": {"type": "string", "enum": TRI_STATE},
                        "signboardType": {"type": ["string", "null"]},
                        "signboardSizeText": {"type": ["string", "null"]},
                        "outdoorSpace": {"type": "string", "enum": TRI_STATE},
                        "outdoorLocation": {"type": ["string", "null"], "enum": ["road_or_sidewalk", "private_land", "terrace", "unknown", None]},
                        "outdoorAreaText": {"type": ["string", "null"]},
                        "outdoorTableCount": {"type": ["integer", "null"]},
                        "delivery": {"type": "string", "enum": TRI_STATE},
                        "cookingFire": {"type": "string", "enum": TRI_STATE},
                        "lpgUse": {"type": "string", "enum": TRI_STATE},
                        "seating": {"type": "string", "enum": TRI_STATE},
                        "takeoutOnly": {"type": "string", "enum": TRI_STATE},
                    },
                    "additionalProperties": False,
                },
                "propertyRights": {
                    "type": "object",
                    "required": ["leaseOrOwnershipStatus", "ownerManagerRelationshipKnown", "managerConsentKnown"],
                    "properties": {
                        "leaseOrOwnershipStatus": {"type": "string", "enum": ["owner", "tenant", "sublease", "before_contract", "unknown"]},
                        "ownerManagerRelationshipKnown": {"type": "string", "enum": TRI_STATE},
                        "managerConsentKnown": {"type": "string", "enum": TRI_STATE},
                    },
                    "additionalProperties": False,
                },
                "documents": {
                    "type": "object",
                    "required": [
                        "leaseContract",
                        "hygieneTraining",
                        "healthCertificate",
                        "fireCertificate",
                        "businessPermitReport",
                        "businessRegistration",
                    ],
                    "properties": {
                        "leaseContract": {"type": "string", "enum": DOCUMENT_STATE},
                        "hygieneTraining": {"type": "string", "enum": DOCUMENT_STATE},
                        "healthCertificate": {"type": "string", "enum": DOCUMENT_STATE},
                        "fireCertificate": {"type": "string", "enum": DOCUMENT_STATE},
                        "businessPermitReport": {"type": "string", "enum": DOCUMENT_STATE},
                        "businessRegistration": {"type": "string", "enum": DOCUMENT_STATE},
                    },
                    "additionalProperties": False,
                },
                "timeline": {
                    "type": "object",
                    "required": ["openingDate", "openingDateText"],
                    "properties": {
                        "openingDate": {"type": ["string", "null"], "description": "YYYY-MM-DD if explicit"},
                        "openingDateText": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["slot", "text", "interpretation"],
                "properties": {
                    "slot": {"type": "string"},
                    "text": {"type": "string"},
                    "interpretation": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "missingCandidates": {
            "type": "object",
            "required": ["requiredForRouteScreening", "requiredForBuildingCheck", "recommendedForChecklist", "laterForProgress"],
            "properties": {
                "requiredForRouteScreening": {"type": "array", "items": {"type": "string"}},
                "requiredForBuildingCheck": {"type": "array", "items": {"type": "string"}},
                "recommendedForChecklist": {"type": "array", "items": {"type": "string"}},
                "laterForProgress": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


COMPACT_SLOT_OUTPUT_CONTRACT: dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "intent": {
        "name": [
            "food_business_precheck",
            "signboard_permit_check",
            "outdoor_space_permit_check",
            "business_change_check",
            "document_readiness_check",
            "building_use_check",
            "takeover_history_check",
            "unknown",
        ],
        "confidence": "0..1",
    },
    "slots": {
        "location": {
            "rawText": "원문 위치 조각 또는 null",
            "regionHint": "예: 마포구 망원동 또는 null",
            "district": "예: 마포구 또는 null",
            "neighborhood": "예: 망원동 또는 null",
            "addressQuality": ADDRESS_QUALITY,
            "roadOrLotAddress": "API 조회용 도로명/지번 주소. 상세주소 제외. 없으면 null",
            "detailAddress": "층/호/지하 등 상세주소. 없으면 null",
            "floorNo": "지하층은 음수, 모르면 null",
            "unitNo": "예: 101호 또는 null",
        },
        "business": {
            "concept": ["cafe", "restaurant", "bakery", "bar", "unknown"],
            "requestedBusinessType": [*ALLOWED_BUSINESS_TYPES, None],
            "candidateBusinessTypes": ALLOWED_BUSINESS_TYPES,
            "salesItems": "예: 음료, 디저트, 커피, 식사, 맥주",
            "liquorSales": TRI_STATE,
            "liquorConfidence": "0..1",
            "takeoverOrExistingBusiness": TRI_STATE,
        },
        "space": {
            "areaM2": "number|null",
            "areaPyeong": "number|null",
            "areaSourceText": "예: 15평 또는 null",
            "isBasement": TRI_STATE,
            "isSecondFloorOrHigher": TRI_STATE,
        },
        "facility": {
            "signboard": TRI_STATE,
            "signboardType": "벽면간판/돌출간판/입간판/null",
            "signboardSizeText": "예: 가로 3m 세로 1m 또는 null",
            "outdoorSpace": TRI_STATE,
            "outdoorLocation": ["road_or_sidewalk", "private_land", "terrace", "unknown", None],
            "outdoorAreaText": "string|null",
            "outdoorTableCount": "integer|null",
            "delivery": TRI_STATE,
            "cookingFire": TRI_STATE,
            "lpgUse": TRI_STATE,
            "seating": TRI_STATE,
            "takeoutOnly": TRI_STATE,
        },
        "propertyRights": {
            "leaseOrOwnershipStatus": ["owner", "tenant", "sublease", "before_contract", "unknown"],
            "ownerManagerRelationshipKnown": TRI_STATE,
            "managerConsentKnown": TRI_STATE,
        },
        "documents": {
            "leaseContract": DOCUMENT_STATE,
            "hygieneTraining": DOCUMENT_STATE,
            "healthCertificate": DOCUMENT_STATE,
            "fireCertificate": DOCUMENT_STATE,
            "businessPermitReport": DOCUMENT_STATE,
            "businessRegistration": DOCUMENT_STATE,
        },
        "timeline": {"openingDate": "YYYY-MM-DD|null", "openingDateText": "string|null"},
    },
    "evidence": [{"slot": "string", "text": "원문 조각", "interpretation": "짧게"}],
    "missingCandidates": {
        "requiredForRouteScreening": "string[]",
        "requiredForBuildingCheck": "string[]",
        "recommendedForChecklist": "string[]",
        "laterForProgress": "string[]",
    },
}


def build_slot_filler_prompt(user_text: str) -> dict[str, Any]:
    return {
        "system": SLOT_FILLER_SYSTEM_PROMPT,
        "user": {
            "task": "다음 사용자 입력을 허가온 slot schema에 맞춰 JSON으로 추출하라.",
            "userText": user_text,
            "schemaVersion": SCHEMA_VERSION,
            "outputContract": COMPACT_SLOT_OUTPUT_CONTRACT,
        },
    }


def sample_output() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "intent": {"name": "food_business_precheck", "confidence": 0.98},
        "slots": {
            "location": {
                "rawText": "마포구 망원동",
                "regionHint": "마포구 망원동",
                "district": "마포구",
                "neighborhood": "망원동",
                "addressQuality": "partial",
                "roadOrLotAddress": None,
                "detailAddress": None,
                "floorNo": None,
                "unitNo": None,
            },
            "business": {
                "concept": "cafe",
                "requestedBusinessType": None,
                "candidateBusinessTypes": ["휴게음식점영업", "일반음식점영업"],
                "salesItems": ["음료", "디저트"],
                "liquorSales": "no",
                "liquorConfidence": 0.72,
                "takeoverOrExistingBusiness": "unknown",
            },
            "space": {
                "areaM2": 49.59,
                "areaPyeong": 15,
                "areaSourceText": "15평",
                "isBasement": "unknown",
                "isSecondFloorOrHigher": "unknown",
            },
            "facility": {
                "signboard": "yes",
                "signboardType": None,
                "signboardSizeText": None,
                "outdoorSpace": "yes",
                "outdoorLocation": "unknown",
                "outdoorAreaText": None,
                "outdoorTableCount": None,
                "delivery": "unknown",
                "cookingFire": "unknown",
                "lpgUse": "unknown",
                "seating": "unknown",
                "takeoutOnly": "unknown",
            },
            "propertyRights": {
                "leaseOrOwnershipStatus": "unknown",
                "ownerManagerRelationshipKnown": "unknown",
                "managerConsentKnown": "unknown",
            },
            "documents": {
                "leaseContract": "unknown",
                "hygieneTraining": "unknown",
                "healthCertificate": "unknown",
                "fireCertificate": "unknown",
                "businessPermitReport": "unknown",
                "businessRegistration": "unknown",
            },
            "timeline": {
                "openingDate": None,
                "openingDateText": None,
            },
        },
        "evidence": [
            {"slot": "location.regionHint", "text": "마포구 망원동", "interpretation": "지역 힌트만 있고 API 조회 가능한 상세주소는 없음"},
            {"slot": "space.areaPyeong", "text": "15평", "interpretation": "영업장 면적 15평, 약 49.59㎡"},
            {"slot": "business.concept", "text": "카페", "interpretation": "카페 창업 의도"},
            {"slot": "business.salesItems", "text": "음료와 디저트", "interpretation": "판매 품목"},
            {"slot": "facility.signboard", "text": "간판도 달고", "interpretation": "간판 설치 예정"},
            {"slot": "facility.outdoorSpace", "text": "가게 앞에 테이블", "interpretation": "외부 공간 사용 예정"},
        ],
        "missingCandidates": {
            "requiredForRouteScreening": [],
            "requiredForBuildingCheck": ["detailed_address", "floor_or_unit_if_known"],
            "recommendedForChecklist": ["lease_contract", "owner_or_manager_permission", "takeover_or_existing_business"],
            "laterForProgress": ["hygiene_training", "health_certificate", "fire_certificate"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Print HEOGAON AI slot filler contract.")
    parser.add_argument("--prompt", action="store_true", help="프롬프트/스키마 계약 출력")
    parser.add_argument("--sample", action="store_true", help="데모 문장 기준 기대 출력 예시")
    parser.add_argument(
        "--text",
        default="마포구 망원동에서 15평 카페를 열고 싶어요. 음료와 디저트를 팔고, 간판도 달고, 가게 앞에 테이블을 두고 싶어요.",
    )
    args = parser.parse_args()

    if args.prompt:
        print(json.dumps(build_slot_filler_prompt(args.text), ensure_ascii=False, indent=2))
        return
    print(json.dumps(sample_output(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
