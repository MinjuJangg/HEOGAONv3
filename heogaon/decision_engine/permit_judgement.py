from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HEOGAON_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = HEOGAON_ROOT.parent
DATA_PREPROCESS = HEOGAON_ROOT / "data_preprocess"
if str(DATA_PREPROCESS) not in sys.path:
    sys.path.insert(0, str(DATA_PREPROCESS))

from precheck_cli import (  # noqa: E402
    DEFAULT_INDEX,
    build_building_profile,
    query_past_businesses,
    write_json,
)
from precheck_common import normalize_space  # noqa: E402


FOOD_BUSINESS_DOCS = [
    "영업신고서",
    "위생교육 수료증",
    "건강진단결과서(구 보건증)",
    "임대차계약서",
    "신분증",
    "소방완비증명서: 지하 66㎡ 이상 또는 지상 2층 100㎡ 이상 등 해당 시",
]

FOOD_BUSINESS_STEPS = [
    "건물 소유주/관리인 권한 및 임대 가능 여부 확인",
    "건축물대장 용도/층별용도/면적/위반건축물 표시 확인",
    "동일 장소 기존 업소 및 행정처분 이력 확인",
    "영업신고증 발급",
    "사업자등록증 발급: 사업개시일부터 20일 이내",
]

FOOD_DEPARTMENTS = [
    "구청 위생과/보건위생과: 식품접객업 영업신고",
    "구청 건축과: 건축물 용도, 위반건축물, 용도변경 확인",
    "관할 소방서: 소방완비증명서 대상 여부 확인",
    "세무서: 사업자등록",
]

FOOD_ROUTE_COMBINATIONS = [
    {
        "routeId": "general_restaurant_without_liquor",
        "displayName": "일반음식점 - 주류 판매 없음",
        "businessType": "일반음식점영업",
        "liquorSales": False,
        "intent": "식사/음식점",
    },
    {
        "routeId": "general_restaurant_with_liquor",
        "displayName": "일반음식점 - 주류 판매 있음",
        "businessType": "일반음식점영업",
        "liquorSales": True,
        "intent": "식사/음식점/카페+주류",
    },
    {
        "routeId": "cafe_without_liquor",
        "displayName": "휴게음식점/카페 - 주류 판매 없음",
        "businessType": "휴게음식점영업",
        "liquorSales": False,
        "intent": "카페/분식/패스트푸드",
    },
    {
        "routeId": "cafe_with_liquor",
        "displayName": "휴게음식점/카페 - 주류 판매 있음",
        "businessType": "휴게음식점영업",
        "liquorSales": True,
        "intent": "카페+주류",
    },
    {
        "routeId": "bakery_without_liquor",
        "displayName": "제과점 - 주류 판매 없음",
        "businessType": "제과점영업",
        "liquorSales": False,
        "intent": "베이커리/제과",
    },
    {
        "routeId": "bakery_with_liquor",
        "displayName": "제과점 - 주류 판매 있음",
        "businessType": "제과점영업",
        "liquorSales": True,
        "intent": "베이커리+주류",
    },
]

RESULT_PRIORITY = {
    "possible": 0,
    "needs_use_change_or_department_check": 1,
    "needs_department_check": 2,
    "needs_more_info": 3,
    "needs_rule_mapping": 4,
    "blocked_until_resolved": 5,
    "blocked": 6,
}

LEGAL_BASIS = [
    {
        "id": "food_hygiene_enforcement_decree_article_21_8",
        "title": "식품위생법 시행령 제21조 제8호",
        "summary": "휴게음식점영업과 제과점영업은 음주행위가 허용되지 않고, 일반음식점영업은 식사와 함께 부수적으로 음주행위가 허용됩니다.",
        "url": "https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsId=004097&lsJoLnkSeq=900232309&print=print",
    },
    {
        "id": "building_use_food_location",
        "title": "음식점 창업 가능 건축물 용도 기준",
        "summary": "휴게음식점/제과점은 300㎡ 미만이면 제1종 근린생활시설, 300㎡ 이상이면 제2종 근린생활시설 기준을 보고, 일반음식점은 제2종 근린생활시설 기준을 봅니다.",
        "url": "https://easylaw.go.kr/CSP/CnpClsMain.laf?ccfNo=2&cciNo=1&cnpClsNo=1&csmSeq=839&popMenu=ov",
    },
]


def canonical_business_type(value: str) -> str:
    text = normalize_space(value)
    compact = re.sub(r"[\s_·ㆍ-]+", "", text)
    if "일반음식점" in compact:
        return "일반음식점영업"
    if "휴게음식점" in compact or "카페" in compact or "커피" in compact:
        return "휴게음식점영업"
    if "제과" in compact or "베이커리" in compact:
        return "제과점영업"
    return text


def parse_place_detail(address: str) -> dict:
    text = normalize_space(address)
    floor_no: int | None = None
    floor_gb_cd = ""
    floor_label = ""

    basement = re.search(r"(?:지하|地下|b|B)\s*([0-9]+)\s*층?", text)
    ground = re.search(r"(?:지상\s*)?([0-9]+)\s*층", text)
    if basement:
        floor_no = int(basement.group(1))
        floor_gb_cd = "10"
        floor_label = f"지하 {floor_no}층"
    elif ground:
        floor_no = int(ground.group(1))
        floor_gb_cd = "20"
        floor_label = f"{floor_no}층"
    elif "옥탑" in text:
        floor_no = 0
        floor_gb_cd = "30"
        floor_label = "옥탑"

    ho_match = re.search(r"([A-Za-z]?\d{1,5})\s*호", text)
    dong_match = re.search(r"([A-Za-z]?\d{1,5})\s*동", text)
    return {
        "floorNo": floor_no,
        "floorGbCd": floor_gb_cd,
        "floorLabel": floor_label,
        "hoNm": f"{ho_match.group(1)}호" if ho_match else "",
        "dongNm": f"{dong_match.group(1)}동" if dong_match else "",
    }


def number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def record_use_text(record: dict) -> str:
    keys = ["mainPurpsCdNm", "etcPurps", "regstrKindCdNm", "flrNoNm", "dongNm", "hoNm"]
    return normalize_space(" ".join(str(record.get(key) or "") for key in keys))


def selected_floor_records(building_profile: dict, detail: dict) -> list[dict]:
    floors = ((building_profile.get("records") or {}).get("floor") or [])
    floor_no = detail.get("floorNo")
    floor_gb_cd = detail.get("floorGbCd")
    if floor_no is None:
        return []

    selected = []
    for record in floors:
        record_floor = record.get("flrNo")
        try:
            record_floor = int(record_floor)
        except (TypeError, ValueError):
            continue
        if record_floor != floor_no:
            continue
        if floor_gb_cd and str(record.get("flrGbCd") or "") != floor_gb_cd:
            continue
        selected.append(record)
    return selected


def selected_unit_records(building_profile: dict, detail: dict) -> list[dict]:
    units = ((building_profile.get("records") or {}).get("unit") or [])
    ho_nm = detail.get("hoNm")
    floor_no = detail.get("floorNo")
    if not ho_nm and floor_no is None:
        return []

    selected = []
    for record in units:
        record_text = normalize_space(" ".join(str(value or "") for value in record.values()))
        if ho_nm and ho_nm not in record_text:
            continue
        if floor_no is not None and str(floor_no) not in record_text:
            continue
        selected.append(record)
    return selected


def matching_past_businesses(past: dict, detail: dict) -> list[dict]:
    matches = past.get("matches") or []
    ho_nm = detail.get("hoNm")
    floor_label = detail.get("floorLabel")
    if not ho_nm and not floor_label:
        return matches

    filtered = []
    for item in matches:
        address_blob = normalize_space(f"{item.get('road_address') or ''} {item.get('lot_address') or ''}")
        if ho_nm and ho_nm not in address_blob:
            continue
        if floor_label and floor_label not in address_blob and floor_label.replace(" ", "") not in address_blob.replace(" ", ""):
            continue
        filtered.append(item)
    return filtered or matches


def strip_address_detail_for_lookup(address: str) -> str:
    text = normalize_space(address)
    text = re.sub(r"\s*,\s*(?:지하\s*)?\d+\s*층.*$", "", text)
    text = re.sub(r"\s+(?:지하\s*)?\d+\s*층.*$", "", text)
    text = re.sub(r"\s+[A-Za-z]?\d{1,5}\s*호.*$", "", text)
    return normalize_space(text)


def infer_area_m2(input_area: float | None, floors: list[dict], past_matches: list[dict]) -> dict:
    if input_area is not None:
        return {"areaM2": input_area, "source": "input"}
    if len(floors) == 1 and number_or_none(floors[0].get("area")) is not None:
        return {"areaM2": number_or_none(floors[0].get("area")), "source": "building_floor"}
    for match in past_matches:
        area = number_or_none(match.get("area_m2"))
        if area is not None:
            return {"areaM2": area, "source": "localdata_reference"}
    return {"areaM2": None, "source": "missing"}


def inspect_violation_status(building_profile: dict) -> dict:
    records = building_profile.get("records") or {}
    hit_fields = []
    flagged = []
    for section_name, section_records in records.items():
        for index, record in enumerate(section_records or []):
            for key, value in record.items():
                key_text = str(key).lower()
                if "viol" not in key_text and "위반" not in str(key):
                    continue
                value_text = normalize_space(value)
                hit_fields.append({"section": section_name, "index": index, "field": key, "value": value_text})
                if value_text in {"1", "Y", "y", "예", "위반", "위반건축물"}:
                    flagged.append(hit_fields[-1])

    if flagged:
        return {
            "status": "flagged",
            "label": "위반건축물 표시 의심",
            "evidence": flagged,
            "message": "건축HUB 응답 필드에서 위반 표시로 해석되는 값이 발견되었습니다.",
        }
    if hit_fields:
        return {
            "status": "not_flagged",
            "label": "위반 표시 없음",
            "evidence": hit_fields,
            "message": "응답에 위반 관련 필드는 있었지만 표시값은 발견되지 않았습니다.",
        }
    return {
        "status": "not_available",
        "label": "API 응답 필드 없음",
        "evidence": [],
        "message": "현재 조회한 건축HUB 표제부/층별개요/전유부/지역지구 응답에는 위반건축물 표시 필드가 없습니다. 건축물대장 원문 또는 건축과 확인이 필요합니다.",
    }


def use_context(building_profile: dict, floors: list[dict], units: list[dict]) -> dict:
    summary = building_profile.get("summary") or {}
    selected_text = " ".join(record_use_text(record) for record in [*units, *floors])
    whole_text = " ".join(
        [
            str(summary.get("mainPurpsCdNm") or ""),
            str(summary.get("etcPurps") or ""),
            " ".join(summary.get("floorUses") or []),
            " ".join(summary.get("unitUses") or []),
        ]
    )
    text = normalize_space(selected_text or whole_text)
    return {
        "selectedUseText": normalize_space(selected_text),
        "buildingUseText": normalize_space(whole_text),
        "decisionUseText": text,
    }


def contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def check_status(status: str, label: str, message: str, evidence: Any = None) -> dict:
    return {
        "status": status,
        "label": label,
        "message": message,
        "evidence": evidence,
    }


def base_decision(result: str, label: str, confidence: str = "medium") -> dict:
    return {
        "result": result,
        "label": label,
        "confidence": confidence,
        "reasons": [],
        "blockers": [],
        "warnings": [],
        "requiredChecks": [],
        "requiredDocuments": FOOD_BUSINESS_DOCS,
        "recommendedStepOrder": FOOD_BUSINESS_STEPS,
        "departments": FOOD_DEPARTMENTS,
    }


def build_criteria_checks(
    business_type: str,
    building_profile: dict,
    detail: dict,
    floors: list[dict],
    units: list[dict],
    area_info: dict,
    liquor_sales: bool,
    same_place_matches: list[dict],
    use_context_value: dict,
    violation: dict,
) -> dict:
    canonical = canonical_business_type(business_type)
    use_text = use_context_value.get("decisionUseText") or ""
    area_m2 = area_info.get("areaM2")
    selected_uses = [record_use_text(record) for record in [*units, *floors]]

    if canonical == "일반음식점영업":
        if contains_any(use_text, ["일반음식점"]):
            building_use = check_status(
                "pass",
                "건축물 용도 기준 충족 가능성 높음",
                "층별용도에 일반음식점이 확인됩니다.",
                selected_uses,
            )
        elif contains_any(use_text, ["제2종근린생활시설", "기타제2종근린생활시설"]):
            building_use = check_status(
                "pass_with_check",
                "제2종 근린생활시설 계열 확인",
                "일반음식점은 제2종 근린생활시설 계열에서 가능하나 해당 호실 기재 가능 여부는 건축과 확인이 필요합니다.",
                selected_uses,
            )
        elif contains_any(use_text, ["제1종근린생활시설", "기타제1종근린생활시설"]):
            building_use = check_status(
                "needs_change_or_check",
                "제1종 계열 확인",
                "일반음식점은 제2종 근린생활시설 계열 검토가 필요합니다. 용도변경 또는 담당부서 확인이 필요합니다.",
                selected_uses,
            )
        else:
            building_use = check_status(
                "unknown",
                "음식점 가능 용도 미확인",
                "건축물대장 용도에서 일반음식점/제2종 근린생활시설 계열을 명확히 찾지 못했습니다.",
                selected_uses,
            )
        area_rule = check_status(
            "not_applicable",
            "300㎡ 면적 기준 비대상",
            "일반음식점은 휴게음식점/제과점의 300㎡ 분기 기준을 적용하지 않습니다.",
            area_info,
        )
    elif canonical in {"휴게음식점영업", "제과점영업"}:
        if area_m2 is None:
            area_rule = check_status(
                "needs_input",
                "영업장 면적 필요",
                "휴게음식점/제과점은 300㎡ 미만이면 제1종, 300㎡ 이상이면 제2종 근린생활시설 기준을 검토해야 합니다.",
                area_info,
            )
            required_class = ""
        else:
            required_class = "제1종근린생활시설" if area_m2 < 300 else "제2종근린생활시설"
            area_rule = check_status(
                "pass",
                "300㎡ 면적 기준 계산 완료",
                f"{area_m2:g}㎡ 기준으로 {required_class} 검토 대상입니다.",
                area_info,
            )

        if not required_class:
            building_use = check_status(
                "needs_input",
                "건축물 용도 기준 판정 보류",
                "영업장 면적을 알아야 제1종/제2종 근린생활시설 기준을 확정할 수 있습니다.",
                selected_uses,
            )
        elif contains_any(use_text, [canonical.replace("영업", ""), required_class]):
            building_use = check_status(
                "pass",
                "건축물 용도 기준 충족 가능성 있음",
                f"{required_class} 또는 해당 업종 계열 용도가 확인됩니다.",
                selected_uses,
            )
        elif "근린생활시설" in use_text:
            building_use = check_status(
                "pass_with_check",
                "근린생활시설 계열 확인",
                f"근린생활시설 계열은 확인되지만 {required_class}로 기재 가능한지는 건축과 확인이 필요합니다.",
                selected_uses,
            )
        else:
            building_use = check_status(
                "needs_change_or_check",
                "음식점 가능 용도 미확인",
                f"{required_class} 또는 해당 업종 계열 용도를 명확히 찾지 못했습니다.",
                selected_uses,
            )
    else:
        building_use = check_status("unknown", "업종 룰 없음", "이 업종의 건축물 용도 기준이 아직 정의되지 않았습니다.", selected_uses)
        area_rule = check_status("unknown", "업종 룰 없음", "이 업종의 면적 기준이 아직 정의되지 않았습니다.", area_info)

    if canonical in {"휴게음식점영업", "제과점영업"} and liquor_sales:
        liquor_rule = check_status(
            "fail",
            "주류 판매 불가 조합",
            "휴게음식점/제과점은 음주행위가 허용되지 않는 영업이므로 주류 판매 계획이 있으면 일반음식점 전환 검토가 필요합니다.",
            {"businessType": canonical, "liquorSales": liquor_sales},
        )
    elif canonical == "일반음식점영업" and liquor_sales:
        liquor_rule = check_status(
            "pass",
            "주류 판매 가능 조합",
            "일반음식점은 식사와 함께 부수적으로 음주행위가 허용되는 영업입니다.",
            {"businessType": canonical, "liquorSales": liquor_sales},
        )
    else:
        liquor_rule = check_status(
            "pass",
            "주류 판매 없음",
            "주류 판매 계획이 없어 주류 관련 업종 전환 이슈가 없습니다.",
            {"businessType": canonical, "liquorSales": liquor_sales},
        )

    active_past = [
        item for item in same_place_matches if "영업" in str(item.get("status") or "") or "영업" in str(item.get("detail_status") or "")
    ]
    past_rule = check_status(
        "needs_check" if active_past else "pass",
        "동일 장소 기존 업소 확인" if active_past else "동일 장소 영업 중 이력 없음",
        "같은 장소에 영업/정상 상태 업소 이력이 있어 승계/중복/폐업 처리 여부 확인이 필요합니다."
        if active_past
        else "조회 범위 내에서 같은 장소 영업/정상 상태 업소 이력이 확인되지 않았습니다.",
        active_past,
    )

    floor_no = detail.get("floorNo")
    floor_gb_cd = detail.get("floorGbCd")
    fire_needed = False
    fire_message = "입력된 층/면적만으로는 소방완비증명서 대상 기준에 걸리지 않습니다."
    if area_m2 is None:
        fire_status = "needs_input"
        fire_message = "지하 66㎡ 이상 또는 지상 2층 100㎡ 이상 여부 판단을 위해 영업장 면적이 필요합니다."
    else:
        if floor_gb_cd == "10" and area_m2 >= 66:
            fire_needed = True
            fire_message = "지하층 66㎡ 이상 기준에 해당할 수 있어 소방완비증명서 확인이 필요합니다."
        elif floor_gb_cd == "20" and floor_no is not None and floor_no >= 2 and area_m2 >= 100:
            fire_needed = True
            fire_message = "지상 2층 이상 100㎡ 이상 기준에 해당할 수 있어 소방완비증명서 확인이 필요합니다."
        fire_status = "needs_check" if fire_needed else "pass"

    return {
        "buildingUse": building_use,
        "area300m2": area_rule,
        "liquor": liquor_rule,
        "violationBuilding": {
            "status": "needs_check" if violation.get("status") == "not_available" else violation.get("status"),
            "label": violation.get("label"),
            "message": violation.get("message"),
            "evidence": violation.get("evidence"),
        },
        "samePlaceBusiness": past_rule,
        "fireSafetyCertificate": check_status(
            fire_status,
            "소방완비증명서 대상 확인",
            fire_message,
            {"floorNo": floor_no, "floorGbCd": floor_gb_cd, "areaInfo": area_info},
        ),
    }


def judge_food_business(
    business_type: str,
    building_profile: dict,
    detail: dict,
    floors: list[dict],
    units: list[dict],
    area_info: dict,
    liquor_sales: bool,
    same_place_matches: list[dict],
) -> dict:
    canonical = canonical_business_type(business_type)
    context = use_context(building_profile, floors, units)
    use_text = context["decisionUseText"]
    area_m2 = area_info.get("areaM2")
    violation = inspect_violation_status(building_profile)
    criteria = build_criteria_checks(
        canonical,
        building_profile,
        detail,
        floors,
        units,
        area_info,
        liquor_sales,
        same_place_matches,
        context,
        violation,
    )
    decision = base_decision("needs_department_check", "담당부서 확인 필요")

    if building_profile.get("status") != "ok":
        decision["result"] = "needs_more_info"
        decision["label"] = "건축물대장 조회 필요"
        decision["confidence"] = "low"
        decision["blockers"].append("건축물대장 API 조회가 완료되지 않았습니다.")
        return {**decision, "criteriaChecks": criteria, "useContext": context, "violationCheck": violation}

    if violation["status"] == "flagged":
        decision["result"] = "blocked_until_resolved"
        decision["label"] = "위반건축물 해소 전 진행 보류"
        decision["confidence"] = "high"
        decision["blockers"].append("건축물대장에 위반건축물 표시가 의심됩니다.")

    if not floors and detail.get("floorNo") is not None:
        decision["warnings"].append("상세주소의 층과 일치하는 층별개요 레코드를 찾지 못했습니다.")
    if detail.get("hoNm") and not units:
        decision["warnings"].append("호실 단위 전유부 레코드는 찾지 못했습니다. 일반건축물은 층별개요 기준으로 판단합니다.")
    if violation["status"] == "not_available":
        decision["requiredChecks"].append("건축물대장 원문 또는 건축과에서 위반건축물 표시 여부 확인")

    if canonical in {"휴게음식점영업", "제과점영업"} and liquor_sales:
        decision["result"] = "blocked"
        decision["label"] = "현재 업종으로 불가"
        decision["confidence"] = "high"
        decision["blockers"].append("휴게음식점/제과점 경로에서는 주류 판매가 불가하므로 일반음식점영업 전환 검토가 필요합니다.")
        decision["requiredChecks"].append("주류 판매 계획이 있으면 업종을 일반음식점영업으로 변경 검토")
        return {**decision, "criteriaChecks": criteria, "useContext": context, "violationCheck": violation}

    if canonical == "일반음식점영업":
        if contains_any(use_text, ["일반음식점"]):
            decision["result"] = "possible"
            decision["label"] = "가능 가능성 높음"
            decision["confidence"] = "high"
            decision["reasons"].append("건축물대장 층별용도에 일반음식점이 확인됩니다.")
        elif contains_any(use_text, ["제2종근린생활시설", "기타제2종근린생활시설"]):
            decision["result"] = "possible"
            decision["label"] = "가능 가능성 있음"
            decision["confidence"] = "medium"
            decision["reasons"].append("건축물대장 용도에 제2종근린생활시설 계열이 확인됩니다.")
            decision["requiredChecks"].append("해당 호실/점포가 일반음식점 용도로 기재 가능한지 건축과 확인")
        elif contains_any(use_text, ["제1종근린생활시설", "기타제1종근린생활시설"]):
            decision["result"] = "needs_use_change_or_department_check"
            decision["label"] = "용도변경/담당부서 확인 필요"
            decision["confidence"] = "medium"
            decision["warnings"].append("일반음식점은 제2종근린생활시설 계열 확인이 필요합니다. 현재 판단 기준에는 제1종 계열이 잡힙니다.")
            decision["requiredChecks"].append("제1종에서 일반음식점 가능 여부 또는 제2종 용도변경 필요 여부 확인")
        else:
            decision["result"] = "needs_department_check"
            decision["label"] = "건축과 확인 필요"
            decision["confidence"] = "low"
            decision["warnings"].append("건축물대장 용도에서 일반음식점/제2종근린생활시설 계열을 명확히 찾지 못했습니다.")

    elif canonical in {"휴게음식점영업", "제과점영업"}:
        if area_m2 is None:
            decision["result"] = "needs_more_info"
            decision["label"] = "영업장 면적 필요"
            decision["confidence"] = "medium"
            decision["blockers"].append("휴게음식점/제과점은 300㎡ 기준 판정을 위해 영업장 면적이 필요합니다.")
            decision["requiredChecks"].append("--area-m2 또는 임대차계약/도면 기준 영업장 면적 입력")
        else:
            required_class = "제1종근린생활시설" if area_m2 < 300 else "제2종근린생활시설"
            decision["reasons"].append(f"영업장 면적 기준 {area_m2:g}㎡로 {required_class} 검토 대상입니다.")
            if contains_any(use_text, ["휴게음식점", "제과점", required_class, "근린생활시설"]):
                decision["result"] = "possible"
                decision["label"] = "가능 가능성 있음"
                decision["confidence"] = "medium"
                decision["reasons"].append("건축물대장 용도에 음식/근린생활시설 계열이 확인됩니다.")
                decision["requiredChecks"].append(f"{required_class}로 기재 가능한지 건축과 확인")
            else:
                decision["result"] = "needs_use_change_or_department_check"
                decision["label"] = "용도변경/담당부서 확인 필요"
                decision["confidence"] = "low"
                decision["warnings"].append("건축물대장 용도에서 휴게음식점/제과점/근린생활시설 계열을 명확히 찾지 못했습니다.")
    else:
        decision["result"] = "needs_rule_mapping"
        decision["label"] = "업종 룰 추가 필요"
        decision["confidence"] = "low"
        decision["warnings"].append(f"아직 판단 룰이 정의되지 않은 업종입니다: {business_type}")

    active_past = [item for item in same_place_matches if "영업" in str(item.get("status") or "") or "영업" in str(item.get("detail_status") or "")]
    if active_past:
        decision["warnings"].append("같은 장소에 영업/정상 상태 업소 이력이 있습니다. 승계/중복/폐업 처리 여부를 확인해야 합니다.")
        decision["requiredChecks"].append("같은 장소 기존 업소 폐업 여부 및 행정처분 승계 가능성 확인")

    return {**decision, "criteriaChecks": criteria, "useContext": context, "violationCheck": violation}


def collect_judgement_context(address: str, area_m2: float | None, index: Path, limit: int) -> dict:
    detail = parse_place_detail(address)
    lookup_address = strip_address_detail_for_lookup(address)
    building = build_building_profile(lookup_address)
    floors = selected_floor_records(building, detail)
    units = selected_unit_records(building, detail)
    past_any = query_past_businesses(index, lookup_address, limit, "")
    same_place_matches = matching_past_businesses(past_any, detail)

    same_type_matches_by_type = {}
    area_info_by_type = {}
    for business_type in ["일반음식점영업", "휴게음식점영업", "제과점영업"]:
        past_same_type = query_past_businesses(index, lookup_address, limit, business_type)
        same_type_matches = matching_past_businesses(past_same_type, detail)
        same_type_matches_by_type[business_type] = same_type_matches
        area_info_by_type[business_type] = infer_area_m2(area_m2, floors, same_type_matches or same_place_matches)

    return {
        "address": address,
        "lookupAddress": lookup_address,
        "detail": detail,
        "building": building,
        "floors": floors,
        "units": units,
        "samePlaceMatches": same_place_matches,
        "sameTypeMatchesByType": same_type_matches_by_type,
        "areaInfoByType": area_info_by_type,
    }


def route_sort_key(route: dict) -> tuple[int, str]:
    decision = route.get("decision") or {}
    return (RESULT_PRIORITY.get(decision.get("result"), 99), route.get("displayName") or route.get("routeId") or "")


def summarize_combination(route: dict) -> dict:
    decision = route.get("decision") or {}
    return {
        "routeId": route.get("routeId"),
        "displayName": route.get("displayName"),
        "businessType": route.get("businessType"),
        "liquorSales": route.get("liquorSales"),
        "result": decision.get("result"),
        "label": decision.get("label"),
        "confidence": decision.get("confidence"),
        "primaryReason": (decision.get("reasons") or decision.get("blockers") or decision.get("warnings") or [""])[0],
    }


def evaluate_route_combination(route: dict, context: dict) -> dict:
    business_type = route["businessType"]
    area_info = context["areaInfoByType"].get(business_type) or {"areaM2": None, "source": "missing"}
    decision = judge_food_business(
        business_type,
        context["building"],
        context["detail"],
        context["floors"],
        context["units"],
        area_info,
        route["liquorSales"],
        context["samePlaceMatches"],
    )
    return {
        **route,
        "canonicalBusinessType": canonical_business_type(business_type),
        "areaInference": area_info,
        "sameBusinessTypePastBusinesses": context["sameTypeMatchesByType"].get(business_type, []),
        "decision": decision,
    }


def build_all_combinations(
    address: str,
    area_m2: float | None,
    index: Path = DEFAULT_INDEX,
    limit: int = 10,
) -> dict:
    context = collect_judgement_context(address, area_m2, index, limit)
    combinations = [evaluate_route_combination(route, context) for route in FOOD_ROUTE_COMBINATIONS]
    combinations = sorted(combinations, key=route_sort_key)
    recommended = [summarize_combination(route) for route in combinations if (route.get("decision") or {}).get("result") == "possible"]
    attention = [
        summarize_combination(route)
        for route in combinations
        if (route.get("decision") or {}).get("result")
        in {"needs_use_change_or_department_check", "needs_department_check", "needs_more_info", "blocked_until_resolved"}
    ]
    blocked = [summarize_combination(route) for route in combinations if (route.get("decision") or {}).get("result") == "blocked"]
    return {
        "status": "ok",
        "mode": "all_combinations",
        "input": {
            "address": address,
            "areaM2": area_m2,
        },
        "addressDetail": context["detail"],
        "fetched": {
            "normalizedAddress": context["building"].get("normalized"),
            "buildingParams": context["building"].get("buildingParams"),
            "buildingSummary": context["building"].get("summary"),
            "selectedFloorRecords": context["floors"],
            "selectedUnitRecords": context["units"],
            "samePlacePastBusinesses": context["samePlaceMatches"][:limit],
        },
        "recommendedRoutes": recommended,
        "attentionRoutes": attention,
        "blockedRoutes": blocked,
        "combinations": combinations,
        "legalBasis": LEGAL_BASIS,
    }


def build_judgement(
    address: str,
    business_type: str,
    liquor_sales: bool,
    area_m2: float | None,
    index: Path = DEFAULT_INDEX,
    limit: int = 10,
) -> dict:
    canonical = canonical_business_type(business_type)
    context = collect_judgement_context(address, area_m2, index, limit)
    same_type_matches = context["sameTypeMatchesByType"].get(canonical, [])
    area_info = context["areaInfoByType"].get(canonical) or {"areaM2": None, "source": "missing"}
    decision = judge_food_business(
        canonical,
        context["building"],
        context["detail"],
        context["floors"],
        context["units"],
        area_info,
        liquor_sales,
        context["samePlaceMatches"],
    )
    return {
        "status": "ok",
        "input": {
            "address": address,
            "businessType": business_type,
            "canonicalBusinessType": canonical,
            "liquorSales": liquor_sales,
            "areaM2": area_m2,
        },
        "addressDetail": context["detail"],
        "fetched": {
            "normalizedAddress": context["building"].get("normalized"),
            "buildingParams": context["building"].get("buildingParams"),
            "buildingSummary": context["building"].get("summary"),
            "selectedFloorRecords": context["floors"],
            "selectedUnitRecords": context["units"],
            "areaInference": area_info,
            "samePlacePastBusinesses": context["samePlaceMatches"][:limit],
            "sameBusinessTypePastBusinesses": same_type_matches[:limit],
        },
        "decision": decision,
        "legalBasis": LEGAL_BASIS,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HEOGAON permit judgement engine.")
    parser.add_argument("--address", required=True, help="상세주소까지 포함 가능. 예: 서울특별시 마포구 포은로 63, 1층 101호")
    parser.add_argument("--business-type", help="예: 일반음식점영업, 휴게음식점영업, 제과점영업")
    parser.add_argument("--all-combinations", action="store_true", help="카페/음식점 가능 조합 전체를 평가")
    parser.add_argument("--liquor-sales", action="store_true", help="주류 판매 계획이 있으면 지정")
    parser.add_argument("--area-m2", type=float, help="영업장 면적. 휴게음식점/제과점 300㎡ 기준 판정에 필요")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.all_combinations:
            result = build_all_combinations(
                address=args.address,
                area_m2=args.area_m2,
                index=args.index,
                limit=args.limit,
            )
        else:
            if not args.business_type:
                raise ValueError("--business-type is required unless --all-combinations is used.")
            result = build_judgement(
                address=args.address,
                business_type=args.business_type,
                liquor_sales=args.liquor_sales,
                area_m2=args.area_m2,
                index=args.index,
                limit=args.limit,
            )
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
