from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_slot(
    case: dict[str, Any],
    field: str,
    value: Any,
    user_text: str,
    admin_term: str,
    status: str = "known",
) -> None:
    case["slots"][field] = {
        "field": field,
        "value": value,
        "userText": user_text,
        "adminTerm": admin_term,
        "status": status,
        "updatedAt": now_iso(),
    }


def append_condition(case: dict[str, Any], value: str) -> None:
    current = as_list(slot_value(case, "condition_screening"))
    if value not in current:
        current.append(value)
    set_slot(case, "condition_screening", current, condition_user_text(current), "추가 조건 스크리닝")


def slot_value(case: dict[str, Any], field: str) -> Any:
    slot = case["slots"].get(field)
    if not slot:
        return None
    return slot.get("value")


def slot_known(case: dict[str, Any], field: str) -> bool:
    value = slot_value(case, field)
    return value not in (None, "", "unknown", [])


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def admin_term_for(field: str, value: Any) -> str:
    if field == "business_activity":
        return "업종/판매품목"
    if field == "on_site_consumption":
        return "객석 있음 / 식품접객업 검토" if value is True else "객석 없음 / 포장·배달 검토"
    if field == "manufacturing_or_simple_sale":
        return {
            "cook": "매장 조리",
            "manufacturing_or_processing": "제조·가공",
            "resale_or_simple_sale": "완제품 단순 판매",
        }.get(str(value), "조리·제조 방식")
    if field == "liquor_sales":
        return "주류 판매 검토" if value is True else "주류 판매 없음"
    if field == "condition_screening":
        return "추가 조건 스크리닝"
    if field == "building_use":
        return "건축물대장상 용도"
    if field == "exact_address":
        return "도로명/지번 주소"
    if field == "floor_unit":
        return "층/호수"
    if field == "area":
        return "영업장 면적"
    if field == "signboard_planned":
        return "간판 설치 예정" if value is True else "간판 설치 계획 없음"
    if field == "outdoor_space_planned":
        return "외부공간 사용 예정" if value is True else "외부공간 사용 계획 없음"
    if field == "lease_contract":
        return "임대차계약 상태"
    if field == "owner_consent":
        return "소유자/관리인 승낙 상태"
    if field in {
        "signboard_type",
        "signboard_size",
        "signboard_location",
        "signboard_image",
        "outdoor_location",
        "outdoor_area",
        "hygieneTraining",
        "healthCertificate",
        "fireCertificate",
    }:
        return label_for_field(field)
    return label_for_field(field)


def condition_user_text(values: list[Any]) -> str:
    labels = {
        "signage_planned": "간판/옥외광고물",
        "outdoor_space_planned": "외부 테이블/보도 사용",
        "lpg_use": "LPG 등 가스 사용",
        "online_sales_planned": "온라인/택배 판매",
        "none": "해당 없음",
    }
    return " + ".join(labels.get(str(value), str(value)) for value in values)


def display_value_for_field(field: str, value: Any) -> str:
    if value in (None, "", []):
        return "미확인"
    if value == "unknown":
        return "아직 모름"
    if isinstance(value, bool):
        return "예" if value else "아니요"
    if isinstance(value, list):
        return condition_user_text(value)
    maps = {
        "manufacturing_or_simple_sale": {
            "cook": "매장에서 조리",
            "manufacturing_or_processing": "직접 제조·가공",
            "resale_or_simple_sale": "완제품 판매",
        },
        "takeover_type": {
            "transfer": "기존 가게 인수",
            "new_report": "신규 시작",
        },
        "lease_contract": {
            "prepared": "계약 완료",
            "before_contract": "계약 전",
            "not_prepared": "아직 준비 안 됨",
        },
        "owner_consent": {
            "yes": "승낙 받음",
            "no": "아직 안 받음",
            "owner": "본인 소유",
        },
        "signboard_image": {
            "prepared": "사진 있음",
            "not_prepared": "아직 없음",
        },
        "outdoor_location": {
            "road_or_sidewalk": "보도/도로 위",
            "private_land": "건물 앞 사유지",
            "terrace": "테라스/전용공간",
        },
        "hygieneTraining": {
            "prepared": "준비 완료",
            "not_prepared": "아직 준비 안 됨",
        },
        "healthCertificate": {
            "prepared": "준비 완료",
            "not_prepared": "아직 준비 안 됨",
        },
        "fireCertificate": {
            "prepared": "준비 완료",
            "not_prepared": "아직 준비 안 됨",
            "not_applicable": "해당 없음",
        },
    }
    return maps.get(field, {}).get(str(value), str(value))


def label_for_field(field: str) -> str:
    labels = {
        "business_activity": "업종/판매품목",
        "exact_address": "정확한 주소",
        "floor_unit": "층/호수",
        "area": "영업장 면적",
        "building_use": "건축물 용도",
        "on_site_consumption": "매장 취식 여부",
        "manufacturing_or_simple_sale": "조리·제조 방식",
        "liquor_sales": "주류 판매 여부",
        "signboard_planned": "간판 설치 여부",
        "outdoor_space_planned": "외부공간 사용 여부",
        "condition_screening": "간판·외부공간·가스 등 추가 조건",
        "lease_contract": "임대차계약",
        "owner_consent": "소유자/관리인 승낙",
        "signboard_type": "간판 종류",
        "signboard_size": "간판 크기",
        "signboard_location": "간판 설치 위치",
        "signboard_image": "현장 사진",
        "outdoor_location": "외부공간 위치",
        "outdoor_area": "외부공간 면적",
        "hygieneTraining": "위생교육 수료증",
        "healthCertificate": "건강진단결과서",
        "fireCertificate": "소방완비증명서",
        "takeover_type": "기존 영업 승계 여부",
    }
    return labels.get(field, field)
