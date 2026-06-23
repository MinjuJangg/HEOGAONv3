from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HEOGAON_ROOT = Path(__file__).resolve().parents[1]
INTAKE_DIR = Path(__file__).resolve().parent
DECISION_ENGINE_DIR = HEOGAON_ROOT / "decision_engine"
DATA_PREPROCESS_DIR = HEOGAON_ROOT / "data_preprocess"
if str(INTAKE_DIR) not in sys.path:
    sys.path.insert(0, str(INTAKE_DIR))
if str(DECISION_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(DECISION_ENGINE_DIR))
if str(DATA_PREPROCESS_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_PREPROCESS_DIR))

try:
    from permit_judgement import build_all_combinations
except Exception as exc:  # pragma: no cover - surfaced in JSON output
    build_all_combinations = None
    DECISION_ENGINE_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    DECISION_ENGINE_IMPORT_ERROR = ""

from slot_filler import contract_to_pipeline_slots, fill_slots  # noqa: E402
from scenario_registry import build_scenario_plan  # noqa: E402
from guidance_context import build_ai_guidance_packet  # noqa: E402
from requirement_graph import build_requirement_graph  # noqa: E402
from ai_judgement import run_ai_judgement  # noqa: E402
from inquiry_package import build_inquiry_package  # noqa: E402

try:
    from precheck_cli import DEFAULT_INDEX, build_building_profile, query_past_businesses  # noqa: E402
except Exception as exc:  # pragma: no cover - surfaced in output
    DEFAULT_INDEX = None
    build_building_profile = None
    query_past_businesses = None
    EXTERNAL_CHECK_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    EXTERNAL_CHECK_IMPORT_ERROR = ""


PYEONG_TO_M2 = 3.305785

BUSINESS_TYPES = {
    "general_restaurant": "일반음식점영업",
    "cafe": "휴게음식점영업",
    "bakery": "제과점영업",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_lookup_address(raw: str) -> tuple[str, str]:
    lookup = normalize_space(raw)
    lookup = re.sub(r"\s*,\s*(?:지하\s*)?\d+\s*층.*$", "", lookup)
    lookup = re.sub(r"\s+(?:지하\s*)?\d+\s*층.*$", "", lookup)
    lookup = re.sub(r"\s+[A-Za-z]?\d{1,5}\s*호.*$", "", lookup)
    detail = normalize_space(raw.replace(lookup, "", 1).strip(" ,"))
    return lookup, detail


def as_bool_from_keywords(text: str, positive: list[str], negative: list[str]) -> bool | None:
    compact = re.sub(r"\s+", "", text)
    if any(token in compact for token in negative):
        return False
    if any(token in compact for token in positive):
        return True
    return None


def extract_address(text: str) -> dict[str, Any]:
    cleaned = normalize_space(text)
    detail_pattern = r"(?:\s*,?\s*(?:지하\s*)?\d+\s*층)?(?:\s*,?\s*[A-Za-z]?\d{1,5}\s*호)?"
    road_pattern = (
        r"((?:서울(?:특별시|시)?\s*)?[가-힣]+구\s+"
        r"[가-힣0-9]+(?:로|길|대로)\s*\d+(?:-\d+)?"
        rf"{detail_pattern})"
    )
    lot_pattern = (
        r"((?:서울(?:특별시|시)?\s*)?[가-힣]+구\s+"
        r"[가-힣0-9]+동\s*\d+(?:-\d+)?"
        rf"{detail_pattern})"
    )

    match = re.search(road_pattern, cleaned) or re.search(lot_pattern, cleaned)
    if match:
        raw = match.group(1).strip(" ,.")
        lookup_raw, detail = split_lookup_address(raw)
        full = raw if raw.startswith("서울") else f"서울특별시 {raw}"
        lookup_full = lookup_raw if lookup_raw.startswith("서울") else f"서울특별시 {lookup_raw}"
        return {
            "raw": raw,
            "full": normalize_space(full),
            "lookupAddress": normalize_space(lookup_full),
            "detail": detail,
            "quality": "full",
            "hasDistrict": bool(re.search(r"[가-힣]+구", raw)),
            "hasRoadOrLotNumber": True,
            "hasFloor": bool(re.search(r"(?:지하\s*)?\d+\s*층", raw)),
            "hasUnit": bool(re.search(r"[A-Za-z]?\d{1,5}\s*호", raw)),
            "source": "text",
        }

    district = re.search(r"([가-힣]+구)", cleaned)
    neighborhood = re.search(r"([가-힣0-9]+동)", cleaned)
    partial = " ".join(part for part in [district.group(1) if district else "", neighborhood.group(1) if neighborhood else ""] if part)
    return {
        "raw": partial,
        "full": "",
        "lookupAddress": "",
        "detail": "",
        "quality": "partial" if partial else "missing",
        "hasDistrict": bool(district),
        "hasRoadOrLotNumber": False,
        "hasFloor": bool(re.search(r"(?:지하\s*)?\d+\s*층", cleaned)),
        "hasUnit": bool(re.search(r"[A-Za-z]?\d{1,5}\s*호", cleaned)),
        "source": "text" if partial else "missing",
    }


def extract_area(text: str) -> dict[str, Any]:
    cleaned = normalize_space(text)
    pyeong = re.search(r"(\d+(?:\.\d+)?)\s*(?:평|py|pyeong)", cleaned, re.IGNORECASE)
    if pyeong:
        value = float(pyeong.group(1))
        return {
            "areaM2": round(value * PYEONG_TO_M2, 2),
            "areaPyeong": value,
            "source": "text_pyeong",
            "confidence": "high",
        }

    square_meter = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|㎡|제곱미터|제곱|평방미터)", cleaned, re.IGNORECASE)
    if square_meter:
        value = float(square_meter.group(1))
        return {
            "areaM2": value,
            "areaPyeong": round(value / PYEONG_TO_M2, 2),
            "source": "text_m2",
            "confidence": "high",
        }

    return {
        "areaM2": None,
        "areaPyeong": None,
        "source": "missing",
        "confidence": "none",
    }


def detect_liquor_sales(text: str) -> bool | None:
    return as_bool_from_keywords(
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
            "커피만",
            "음료만",
            "안팔아요",
            "안팔",
            "팔지않",
            "판매안",
            "판매하지않",
            "취급안",
            "취급하지않",
        ],
    )


def extract_business(text: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", "", text)
    liquor_sales = detect_liquor_sales(text)

    explicit_type = None
    if "일반음식점" in compact:
        explicit_type = BUSINESS_TYPES["general_restaurant"]
    elif "휴게음식점" in compact:
        explicit_type = BUSINESS_TYPES["cafe"]
    elif "제과점" in compact:
        explicit_type = BUSINESS_TYPES["bakery"]

    concept = "unknown"
    if any(token in compact for token in ["카페", "커피", "음료", "디저트", "브런치"]):
        concept = "cafe"
    if any(token in compact for token in ["음식점", "식당", "레스토랑", "파스타", "분식", "밥집", "요리"]):
        concept = "restaurant"
    if any(token in compact for token in ["베이커리", "빵집", "제과"]):
        concept = "bakery"
    if any(token in compact for token in ["술집", "주점", "호프", "펍", "바"]):
        concept = "bar"

    if liquor_sales is None and concept == "cafe" and any(token in compact for token in ["음료", "커피", "디저트", "빵", "케이크"]):
        liquor_sales = False

    if explicit_type:
        candidates = [explicit_type]
    elif concept == "bakery":
        candidates = [BUSINESS_TYPES["bakery"]]
    elif concept == "restaurant" or concept == "bar":
        candidates = [BUSINESS_TYPES["general_restaurant"]]
    elif concept == "cafe":
        candidates = [BUSINESS_TYPES["cafe"], BUSINESS_TYPES["general_restaurant"]]
    else:
        candidates = [BUSINESS_TYPES["cafe"], BUSINESS_TYPES["general_restaurant"], BUSINESS_TYPES["bakery"]]

    if liquor_sales is True and BUSINESS_TYPES["general_restaurant"] not in candidates:
        candidates.append(BUSINESS_TYPES["general_restaurant"])

    return {
        "rawText": text,
        "concept": concept,
        "requestedType": explicit_type,
        "candidateTypes": candidates,
        "liquorSales": liquor_sales,
        "confidence": "high" if concept != "unknown" or explicit_type else "low",
    }


def extract_facility_flags(text: str) -> dict[str, Any]:
    return {
        "signboard": as_bool_from_keywords(text, ["간판", "옥외광고"], ["간판안", "간판없"]),
        "outdoorSpace": as_bool_from_keywords(
            text,
            ["외부좌석", "외부 좌석", "테라스", "야장", "노상", "도로점용", "가게앞", "가게 앞", "앞에테이블", "앞에 테이블", "밖에 테이블"],
            ["외부좌석안", "테라스없"],
        ),
        "delivery": as_bool_from_keywords(text, ["배달", "포장", "테이크아웃"], ["배달안", "포장안"]),
        "cookingFire": as_bool_from_keywords(text, ["조리", "주방", "가스", "불사용", "튀김"], ["조리안", "불사용안"]),
        "lpgUse": as_bool_from_keywords(
            text,
            ["LPG", "LP가스", "액화석유가스", "가스화구", "가스 화구", "가스버너", "가스레인지", "가스렌지", "화구", "숯불"],
            ["LPG안", "가스안", "가스사용안", "가스사용하지않", "가스없", "화구없"],
        ),
    }


def extract_document_status(text: str) -> dict[str, str]:
    compact = re.sub(r"\s+", "", text)
    docs = {
        "hygieneTraining": ["위생교육", "교육수료"],
        "healthCertificate": ["보건증", "건강진단결과서"],
        "leaseContract": ["임대차", "계약서"],
        "idCard": ["신분증"],
        "fireCertificate": ["소방필증", "소방완비", "안전시설등완비"],
        "businessRegistration": ["사업자등록"],
        "businessPermitReport": ["영업신고증", "영업신고"],
    }
    result: dict[str, str] = {}
    for key, tokens in docs.items():
        result[key] = "prepared" if any(token in compact for token in tokens) else "unknown"
    return result


def question(
    id_: str,
    label: str,
    question_text: str,
    reason: str,
    examples: list[str],
    answer_type: str = "text",
) -> dict[str, Any]:
    return {
        "id": id_,
        "label": label,
        "question": question_text,
        "reason": reason,
        "examples": examples,
        "answerType": answer_type,
    }


def build_missing_info(slots: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if slots.get("intent") == "signboard_permit_check":
        return build_signboard_missing_info(slots)
    if slots.get("intent") == "outdoor_space_permit_check":
        return build_outdoor_space_missing_info(slots)
    if slots.get("intent") == "takeover_history_check":
        return build_takeover_history_missing_info(slots)
    if slots.get("intent") == "building_use_check":
        return build_building_use_missing_info(slots)
    if slots.get("intent") == "document_readiness_check":
        return build_document_readiness_missing_info(slots)

    required_now: list[dict[str, Any]] = []
    recommended_next: list[dict[str, Any]] = []
    later: list[dict[str, Any]] = []

    address = slots["address"]
    business = slots["business"]
    area = slots["space"]
    facility = slots["facility"]
    docs = slots["documents"]

    if business["confidence"] == "low":
        required_now.append(
            question(
                "business_concept",
                "업종/판매품목",
                "어떤 가게를 열 계획인지 알려주세요.",
                "카페/일반음식점/제과점 후보를 정해야 영업신고 경로가 갈립니다.",
                ["카페", "브런치 카페", "일반음식점", "베이커리"],
            )
        )

    if business["liquorSales"] is None:
        required_now.append(
            question(
                "liquor_sales",
                "주류 판매",
                "주류를 판매할 계획이 있나요?",
                "휴게음식점/제과점은 주류 판매가 막히고, 주류가 있으면 일반음식점 경로를 같이 봐야 합니다.",
                ["주류 판매 없음", "맥주/와인 판매 예정", "아직 미정"],
                "boolean_or_unknown",
            )
        )

    if address["quality"] != "full":
        known_area = f"현재 입력된 위치: {address['raw']}. " if address.get("raw") else ""
        required_now.append(
            question(
                "detailed_address",
                "사업장 전체 주소",
                "사업장 주소를 도로명/지번과 층/호수까지 알려주세요.",
                known_area + "도로명/지번 주소가 있어야 건축물대장을 조회할 수 있고, 층/호수까지 있으면 같은 장소 이력과 소방/층별 용도 확인이 더 정확해집니다.",
                ["서울특별시 마포구 포은로 63", "마포구 포은로 63, 1층 101호"],
            )
        )
    elif not address["hasFloor"]:
        required_now.append(
            question(
                "floor_unit",
                "층/호수",
                "현재 주소에 이어서 층과 호수도 알려주세요.",
                "도로명/지번은 확인됐고, 층/호가 있으면 층별 용도, 소방완비증명서 기준, 같은 장소 기존 업소 매칭이 더 정확해집니다.",
                ["1층 101호", "지하 1층", "2층"],
            )
        )

    if area["areaM2"] is None:
        required_now.append(
            question(
                "area",
                "영업장 면적",
                "영업장 면적을 알고 있나요?",
                "휴게음식점/제과점 300㎡ 기준과 소방완비증명서 기준에 필요합니다. API에서 추정할 수 있어도 임대 면적이 우선입니다.",
                ["15평", "49.5㎡", "아직 모름"],
                "number_or_unknown",
            )
        )

    if facility["signboard"] is None:
        recommended_next.append(
            question(
                "signboard",
                "간판",
                "외부 간판을 설치할 예정인가요?",
                "간판이 있으면 옥외광고물 신고/허가 여부와 도시경관 담당 부서 안내가 필요합니다.",
                ["전면 간판 1개", "간판 없음", "아직 미정"],
                "boolean_or_unknown",
            )
        )

    if facility["outdoorSpace"] is None:
        recommended_next.append(
            question(
                "outdoor_space",
                "외부 공간",
                "테라스나 외부 좌석처럼 밖의 공간을 사용할 계획이 있나요?",
                "외부 공간을 쓰면 도로점용 또는 별도 부서 확인이 필요할 수 있습니다.",
                ["테라스 있음", "외부 좌석 없음", "미정"],
                "boolean_or_unknown",
            )
        )

    if docs["leaseContract"] == "unknown":
        recommended_next.append(
            question(
                "lease_contract",
                "임대차계약",
                "임대차계약서 또는 사용권한을 확인할 수 있나요?",
                "영업신고 서류와 건물 소유자/관리인 권한 확인에 필요합니다.",
                ["계약 완료", "계약 전", "관리인 통해 계약 예정"],
                "choice",
            )
        )

    doc_questions = [
        ("hygieneTraining", "위생교육 수료증"),
        ("healthCertificate", "건강진단결과서"),
        ("fireCertificate", "소방완비증명서"),
    ]
    for key, label in doc_questions:
        if docs[key] == "unknown":
            later.append(
                question(
                    key,
                    label,
                    f"{label} 준비 여부를 나중에 확인해야 합니다.",
                    "영업신고 제출 전 체크리스트 상태 관리에 필요합니다.",
                    ["준비 완료", "발급 예정", "해당 여부 모름"],
                    "choice",
                )
            )

    return {
        "requiredNow": required_now,
        "recommendedNext": recommended_next,
        "later": later,
    }


def build_signboard_missing_info(slots: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    required_now = []
    if slots["address"]["quality"] != "full":
        required_now.append(
            question(
                "address",
                "설치 장소 주소",
                "간판을 설치할 건물 주소를 알려주세요.",
                "지자체 담당 부서와 옥외광고물 표시 기준은 설치 장소를 기준으로 확인합니다.",
                ["서울특별시 마포구 포은로 63", "마포구 망원동 ○○로 12"],
            )
        )
    required_now.extend(
        [
            question("signboard_type", "간판 종류", "어떤 간판을 설치하거나 변경하려고 하나요?", "벽면간판, 돌출간판, 입간판, 현수막 등 종류에 따라 허가/신고 기준이 달라집니다.", ["벽면 간판", "돌출 간판", "입간판", "현수막"]),
            question("signboard_size", "간판 크기", "간판의 대략적인 가로/세로 크기나 면적을 알고 있나요?", "간판 크기와 설치 높이에 따라 허가/신고/심의 여부가 갈릴 수 있습니다.", ["가로 3m 세로 1m", "5㎡ 정도", "아직 모름"]),
        ]
    )
    recommended_next = [
        question("owner_consent", "설치 승낙", "건물주 또는 관리인에게 간판 설치 승낙을 받았나요?", "타인 소유 건물/대지에 표시하는 경우 사용 승낙서가 필요할 수 있습니다.", ["승낙 받음", "아직 안 받음", "본인 소유 건물"]),
        question("signboard_image", "현장 사진", "간판 설치 예정 위치 사진이 있나요?", "신청 서류나 부서 문의 시 설치 위치 사진이 필요할 수 있습니다.", ["사진 있음", "아직 없음"]),
    ]
    return {"requiredNow": required_now, "recommendedNext": recommended_next, "later": []}


def build_outdoor_space_missing_info(slots: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    required_now = []
    if slots["address"]["quality"] != "full":
        required_now.append(
            question("address", "사용 장소 주소", "외부 테이블을 둘 사업장 주소를 알려주세요.", "도로/보도 점용 여부와 담당 부서는 위치 기준으로 확인합니다.", ["서울특별시 마포구 포은로 63"])
        )
    required_now.extend(
        [
            question("outdoor_location", "외부공간 위치", "테이블을 둘 곳이 보도/도로인가요, 건물 사유지인가요?", "공공도로/보도 여부에 따라 도로점용 확인이 필요할 수 있습니다.", ["보도 위", "건물 앞 사유지", "잘 모름"]),
            question("outdoor_area", "사용 면적", "외부에 둘 테이블 수나 사용 면적을 알고 있나요?", "사용 면적과 위치가 문의/허가 판단에 필요합니다.", ["2인 테이블 2개", "약 3㎡", "아직 모름"]),
        ]
    )
    return {"requiredNow": required_now, "recommendedNext": [], "later": []}


def build_takeover_history_missing_info(slots: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    required_now = [
        question("detailed_address", "기존 업소 전체 주소", "인수하려는 업소의 도로명/지번 주소와 층/호수를 알려주세요.", "같은 장소의 기존 인허가/행정처분 이력은 주소와 층/호 기준으로 매칭해야 정확합니다.", ["서울특별시 마포구 포은로 63, 1층 101호"]),
        question("target_business_type", "확인할 업종", "확인하려는 업종이 무엇인가요?", "동일 업종 이력과 행정처분 여부를 좁히기 위해 필요합니다.", ["카페/휴게음식점", "일반음식점", "제과점", "아직 모름"]),
    ]
    recommended_next = [
        question("takeover_status", "인수 상태", "이미 인수 계약을 했나요, 검토 중인가요?", "계약 전이면 리스크 확인 결과를 계약 판단에 먼저 반영할 수 있습니다.", ["계약 전", "계약 완료", "검토 중"]),
    ]
    return {"requiredNow": required_now, "recommendedNext": recommended_next, "later": []}


def build_building_use_missing_info(slots: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    required_now = [
        question("detailed_address", "건축물/사업장 전체 주소", "확인할 건물의 도로명/지번 주소와 층/호수를 알려주세요.", "건축물대장 조회에는 도로명/지번 주소가 필요하고, 층/호수는 층별 용도와 전유부 확인에 필요합니다.", ["서울특별시 마포구 포은로 63, 1층 101호"]),
        question("target_business_type", "희망 업종", "어떤 업종 가능 여부를 확인하려고 하나요?", "일반음식점/휴게음식점/제과점에 따라 용도 기준이 달라집니다.", ["일반음식점", "휴게음식점/카페", "제과점", "아직 모름"]),
    ]
    return {"requiredNow": required_now, "recommendedNext": [], "later": []}


def build_document_readiness_missing_info(slots: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    required_now = []
    if not slots["business"]["candidateTypes"]:
        required_now.append(
            question(
                "target_permit_or_business_type",
                "확인할 업종",
                "어떤 영업신고 또는 업종의 서류를 확인하려고 하나요?",
                "일반음식점/휴게음식점/제과점에 따라 위생교육 기관과 일부 준비 항목이 달라질 수 있습니다.",
                ["휴게음식점/카페", "일반음식점", "제과점", "아직 모름"],
            )
        )
    recommended_next = []
    docs = slots["documents"]
    labels = {
        "leaseContract": "임대차계약서",
        "hygieneTraining": "위생교육 수료증",
        "healthCertificate": "건강진단결과서",
        "fireCertificate": "소방완비증명서",
        "businessPermitReport": "영업신고증",
        "businessRegistration": "사업자등록증",
    }
    for key, label in labels.items():
        if docs.get(key) == "unknown":
            recommended_next.append(
                question(
                    key,
                    label,
                    f"{label} 준비 여부를 알려주세요.",
                    "현재 준비상태를 알아야 영업신고 전/후 순서와 남은 일을 정리할 수 있습니다.",
                    ["준비 완료", "아직 없음", "해당 여부 모름"],
                    "choice",
                )
            )
    return {"requiredNow": required_now, "recommendedNext": recommended_next, "later": []}


def build_preliminary_diagnosis(slots: dict[str, Any]) -> dict[str, Any]:
    if slots.get("intent") == "signboard_permit_check":
        return build_signboard_diagnosis(slots)
    if slots.get("intent") == "outdoor_space_permit_check":
        return build_outdoor_space_diagnosis(slots)
    if slots.get("intent") == "takeover_history_check":
        return build_takeover_history_diagnosis(slots)
    if slots.get("intent") == "building_use_check":
        return build_building_use_diagnosis(slots)
    if slots.get("intent") == "document_readiness_check":
        return build_document_readiness_diagnosis(slots)

    business = slots["business"]
    area = slots["space"]
    facility = slots["facility"]
    address = slots["address"]
    liquor_sales = business["liquorSales"]
    area_m2 = area["areaM2"]

    routes = []
    for route_source in business.get("candidateRoutes") or [{"businessType": item} for item in business["candidateTypes"]]:
        business_type = route_source["businessType"]
        route = {
            "businessType": business_type,
            "status": "preliminary_possible" if route_source.get("status") == "candidate" else route_source.get("status", "preliminary_possible"),
            "label": "1차 후보" if route_source.get("status") == "candidate" else "확인 필요 후보",
            "score": route_source.get("score"),
            "reasons": list(route_source.get("reasons") or []),
            "blockedBy": [],
            "needsForFinal": ["상세주소", "건축물대장 용도 확인", "위반건축물 여부 확인"],
            "sourceReferences": route_source.get("sourceReferences") or [],
        }

        if business_type in {"휴게음식점영업", "제과점영업"}:
            if liquor_sales is True:
                route["status"] = "blocked_by_business_rule"
                route["label"] = "주류 판매 조합 불가"
                route["blockedBy"].append("휴게음식점/제과점은 주류 판매 경로로 보기 어렵습니다.")
                route["needsForFinal"] = []
            elif area_m2 is None:
                route["status"] = "needs_more_info"
                route["label"] = "면적 확인 필요"
                route["reasons"].append("300㎡ 미만/이상에 따라 제1종/제2종 근린생활시설 기준이 달라집니다.")
            elif area_m2 < 300:
                route["reasons"].append(f"{area_m2:g}㎡ 기준 300㎡ 미만입니다. 제1종 근린생활시설 기준을 우선 검토합니다.")
            else:
                route["reasons"].append(f"{area_m2:g}㎡ 기준 300㎡ 이상입니다. 제2종 근린생활시설 기준을 우선 검토합니다.")

        if business_type == "일반음식점영업":
            if liquor_sales is True:
                route["reasons"].append("주류 판매 계획이 있으면 일반음식점 경로를 우선 검토합니다.")
            elif liquor_sales is False:
                route["reasons"].append("주류 판매가 없어도 조리/식사 제공 방식이면 일반음식점 후보가 될 수 있습니다.")
            else:
                route["reasons"].append("주류 판매 여부와 조리 방식에 따라 일반음식점 후보 여부가 달라집니다.")

        routes.append(route)

    checks = []
    if liquor_sales is None:
        checks.append({"id": "liquor", "status": "needs_input", "label": "주류 판매 여부 확인 필요"})
    elif liquor_sales:
        checks.append({"id": "liquor", "status": "route_split", "label": "주류 판매 계획 있음: 일반음식점 경로 우선 검토"})
    else:
        checks.append({"id": "liquor", "status": "pass", "label": "주류 판매 계획 없음"})

    if area_m2 is None:
        checks.append({"id": "area300m2", "status": "needs_input", "label": "영업장 면적 필요"})
    elif area_m2 < 300:
        checks.append({"id": "area300m2", "status": "pass", "label": f"{area_m2:g}㎡: 300㎡ 미만"})
    else:
        checks.append({"id": "area300m2", "status": "pass", "label": f"{area_m2:g}㎡: 300㎡ 이상"})

    if facility["signboard"] is True:
        checks.append({"id": "signboard", "status": "needs_department_check", "label": "간판 설치 예정: 옥외광고물 신고/허가 확인 필요"})
    elif facility["signboard"] is False:
        checks.append({"id": "signboard", "status": "pass", "label": "간판 설치 계획 없음"})
    else:
        checks.append({"id": "signboard", "status": "unknown", "label": "간판 설치 여부 미확인"})

    if facility["outdoorSpace"] is True:
        checks.append({"id": "outdoor_space", "status": "needs_department_check", "label": "외부 테이블/공간 사용 예정: 도로점용 또는 외부공간 사용 확인 필요"})
    elif facility["outdoorSpace"] is False:
        checks.append({"id": "outdoor_space", "status": "pass", "label": "외부 공간 사용 계획 없음"})
    else:
        checks.append({"id": "outdoor_space", "status": "unknown", "label": "외부 공간 사용 여부 미확인"})

    if address["quality"] == "full":
        next_gate = {
            "id": "building_property_check",
            "status": "ready",
            "label": "상세주소가 있어 건축물대장/API 기반 검증으로 진행 가능",
        }
    else:
        next_gate = {
            "id": "building_property_check",
            "status": "waiting_for_detailed_address",
            "label": "상세주소를 받으면 건축물 용도, 위반건축물 여부, 기존 업소 이력을 확인합니다.",
        }

    return {
        "level": "preliminary",
        "summary": "상세주소 전 단계의 1차 사전진단입니다. 업종 경로와 명백한 분기 조건은 판단하고, 건물/입지 검증은 다음 단계로 넘깁니다.",
        "routes": routes,
        "checks": checks,
        "commonDocuments": [
            "식품 영업 신고서",
            "위생교육 수료증",
            "건강진단결과서",
            "임대차계약서 또는 시설사용계약서",
            "신분증",
            "소방완비증명서: 층/면적 조건 해당 시",
        ],
        "nextGate": next_gate,
    }


def build_signboard_diagnosis(slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "preliminary",
        "summary": "간판 설치/변경에 대한 1차 인허가 진단입니다. 업종 창업 판단이 아니라 옥외광고물 표시허가 또는 신고 여부를 확인합니다.",
        "routes": [
            {
                "permitType": "옥외광고물 등의 표시허가(신고)",
                "status": "needs_department_check",
                "label": "간판 인허가 후보",
                "reasons": [
                    "간판, 현수막, 돌출간판, 입간판 등은 옥외광고물 허가 또는 신고 대상이 될 수 있습니다.",
                    "간판 종류, 크기, 설치 위치, 조명/전광류 여부에 따라 허가/신고/심의 여부가 갈립니다.",
                ],
                "needsForFinal": ["사업장 주소", "간판 종류", "간판 크기", "설치 위치 사진", "건물/대지 사용 승낙 여부"],
                "sourceReferences": [
                    {
                        "title": "정부24 옥외광고물 등의 표시허가(신고)",
                        "url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&tp_seq=02",
                        "summary": "옥외광고물 등을 허가 또는 신고하려는 민원사무입니다.",
                    },
                    {
                        "title": "옥외광고물법 및 시행령 허가ㆍ신고 대상 안내",
                        "url": "https://www.easylaw.go.kr/CSP/CnpClsMainBtr.laf?ccfNo=3&cciNo=1&cnpClsNo=1&csmSeq=897",
                        "summary": "광고물 종류와 규모에 따라 허가 또는 신고 대상이 나뉩니다.",
                    },
                ],
            }
        ],
        "checks": [
            {"id": "signboard_type", "status": "needs_input", "label": "간판 종류 확인 필요"},
            {"id": "signboard_size", "status": "needs_input", "label": "간판 크기/면적 확인 필요"},
            {"id": "owner_consent", "status": "needs_input", "label": "건물 또는 대지 사용 승낙 여부 확인 필요"},
        ],
        "commonDocuments": [
            "옥외광고물 표시허가 신청서 또는 신고서",
            "건물/대지 사용 승낙서",
            "위치도 또는 약도",
            "건물 전경사진 및 설치 예정 위치 사진",
            "광고물 원색도안",
            "설계도/시방서: 허가ㆍ심의ㆍ구조 확인 대상인 경우",
        ],
        "nextGate": {
            "id": "signboard_detail_check",
            "status": "waiting_for_signboard_details",
            "label": "간판 종류, 크기, 설치 위치를 받으면 허가/신고/부서 문의 항목을 더 좁힙니다.",
        },
    }


def build_outdoor_space_diagnosis(slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "preliminary",
        "summary": "외부 테이블/테라스 사용에 대한 1차 인허가 진단입니다. 도로점용 또는 사유지 사용 권한 확인이 핵심입니다.",
        "routes": [
            {
                "permitType": "도로점용 또는 외부공간 사용 확인",
                "status": "needs_department_check",
                "label": "외부공간 사용 확인 필요",
                "reasons": [
                    "가게 앞 테이블이 보도ㆍ도로 등 공공공간을 점유하면 도로점용 확인이 필요할 수 있습니다.",
                    "사유지라도 건물주/관리인 사용 승낙 여부 확인이 필요합니다.",
                ],
                "needsForFinal": ["사업장 주소", "외부공간 위치", "공공도로/보도 여부", "테이블 수", "사용 면적"],
                "sourceReferences": [],
            }
        ],
        "checks": [
            {"id": "public_road_or_private_land", "status": "needs_input", "label": "외부공간이 도로/보도인지 사유지인지 확인 필요"},
            {"id": "outdoor_area", "status": "needs_input", "label": "사용 면적과 테이블 수 확인 필요"},
        ],
        "commonDocuments": ["위치도", "현장 사진", "사용 면적 도면", "소유자/관리인 승낙서: 사유지인 경우"],
        "nextGate": {
            "id": "outdoor_space_detail_check",
            "status": "waiting_for_outdoor_space_details",
            "label": "외부공간 위치와 사용 면적을 받으면 담당 부서 문의 항목을 좁힙니다.",
        },
    }


def build_takeover_history_diagnosis(slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "preliminary",
        "summary": "기존 업소 인수 또는 동일 장소 행정처분 이력 확인에 대한 1차 진단입니다.",
        "routes": [
            {
                "permitType": "동일 장소 기존 업소/행정처분 이력 조회",
                "status": "waiting_for_address",
                "label": "이력 조회 필요",
                "reasons": [
                    "같은 장소에 동일 또는 유사 업종이 있었는지 확인해야 합니다.",
                    "기존 업소의 행정처분 이력이 새 영업신고 리스크가 될 수 있어 담당 부서 확인이 필요합니다.",
                ],
                "needsForFinal": ["상세주소", "확인할 업종", "기존 상호 또는 인수 대상 정보"],
                "sourceReferences": [],
            }
        ],
        "checks": [
            {"id": "same_place_history", "status": "needs_input", "label": "상세주소 기준 기존 업소 이력 조회 필요"},
            {"id": "administrative_disposition", "status": "needs_department_check", "label": "행정처분 승계/영향 여부 담당 부서 확인 필요"},
        ],
        "commonDocuments": ["임대차계약서 또는 계약 예정 정보", "기존 업소 상호/주소", "양도양수 관련 자료: 해당 시"],
        "nextGate": {
            "id": "same_place_lookup",
            "status": "waiting_for_detailed_address",
            "label": "상세주소를 받으면 LOCALDATA/인허가 이력과 동일 장소 매칭을 진행합니다.",
        },
    }


def build_building_use_diagnosis(slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "preliminary",
        "summary": "건축물 용도와 위반건축물 여부 확인에 대한 1차 진단입니다.",
        "routes": [
            {
                "permitType": "건축물대장 용도/위반건축물 확인",
                "status": "waiting_for_address",
                "label": "건축물대장 조회 필요",
                "reasons": [
                    "업종 가능 여부는 건축물 주용도, 층별용도, 전유부 용도, 위반건축물 여부를 확인해야 좁힐 수 있습니다.",
                    "주소와 희망 업종을 받으면 건축물대장 API 기반으로 다음 판단을 진행합니다.",
                ],
                "needsForFinal": ["상세주소", "희망 업종", "층/호수"],
                "sourceReferences": [],
            }
        ],
        "checks": [
            {"id": "building_ledger", "status": "needs_input", "label": "건축물대장 조회용 상세주소 필요"},
            {"id": "target_business_type", "status": "needs_input", "label": "검토할 업종 필요"},
        ],
        "commonDocuments": ["건축물대장 열람 결과", "임대차계약서 또는 도면: 면적 확인용"],
        "nextGate": {
            "id": "building_ledger_api",
            "status": "waiting_for_detailed_address",
            "label": "상세주소를 받으면 건축물대장 API로 용도/층/면적 확인을 진행합니다.",
        },
    }


def build_document_readiness_diagnosis(slots: dict[str, Any]) -> dict[str, Any]:
    docs = slots["documents"]
    doc_labels = {
        "leaseContract": "임대차계약서 및 사용권한 확인",
        "hygieneTraining": "위생교육 수료증",
        "healthCertificate": "건강진단결과서",
        "fireCertificate": "소방완비증명서: 층/면적 조건 해당 시",
        "businessPermitReport": "영업신고증",
        "businessRegistration": "사업자등록증",
    }
    checklist = [
        {"id": key, "label": label, "status": docs.get(key, "unknown")}
        for key, label in doc_labels.items()
    ]
    return {
        "level": "preliminary",
        "summary": "제출 서류와 진행 순서 중심의 1차 진단입니다. 영업 가능성 판단보다 준비 상태 정리가 우선입니다.",
        "routes": [
            {
                "permitType": "식품 영업신고 서류 준비상태 점검",
                "status": "checklist_ready",
                "label": "서류 체크리스트 생성 가능",
                "reasons": [
                    "사용자가 서류 준비 상태 또는 영업신고/사업자등록 순서를 묻고 있습니다.",
                    "영업신고증은 사업자등록 전 단계에서 먼저 확인해야 하는 핵심 흐름입니다.",
                ],
                "needsForFinal": ["확인할 업종", "현재 준비된 서류", "사업장 주소: 건물/소방 조건을 함께 보려면 필요"],
                "sourceReferences": [],
            }
        ],
        "checks": checklist,
        "commonDocuments": [
            "위생교육 수료증",
            "건강진단결과서",
            "임대차계약서 및 신분증",
            "소방완비증명서: 지하/2층 이상 및 면적 조건 해당 시",
            "영업신고증",
            "사업자등록증: 영업신고증 이후, 사업개시일부터 20일 내 등록",
        ],
        "submissionOrder": [
            "업종 및 건축물 용도 확인",
            "위생교육/건강진단/임대차계약서 등 구비서류 준비",
            "영업신고증 발급",
            "사업자등록증 발급",
        ],
        "nextGate": {
            "id": "document_status_check",
            "status": "waiting_for_document_status" if any(item["status"] == "unknown" for item in checklist) else "ready_for_submission_order",
            "label": "준비된 서류와 아직 없는 서류를 받으면 제출 순서를 정리합니다.",
        },
    }


def build_diagnosis_flow(slots: dict[str, Any], api_plan: dict[str, Any]) -> dict[str, Any]:
    if slots.get("intent") == "signboard_permit_check":
        return {
            "currentStage": "signboard_detail_screening",
            "stages": [
                {"id": "intent_classification", "label": "민원 목적 분류", "status": "done", "outputs": ["간판 설치/변경 목적"]},
                {"id": "signboard_detail_screening", "label": "간판 허가/신고 1차 분류", "status": "waiting_for_input", "requiredInputs": ["address", "signboard_type", "signboard_size"], "outputs": ["허가/신고/심의 가능성", "필요 서류"]},
                {"id": "department_guide", "label": "담당 부서 문의 가이드", "status": "after_detail_check", "outputs": ["도시경관/옥외광고물 담당 부서", "문의 문장"]},
            ],
            "boundary": {
                "serviceIntentRole": "사용자 목적이 창업인지, 간판 추가인지 먼저 분류합니다.",
                "canJudgeNow": ["간판 허가/신고 민원으로 분기", "공통 구비서류 안내"],
                "needsMoreInfo": ["간판 종류", "간판 크기", "설치 위치", "건물 사용 승낙 여부"],
            },
        }
    if slots.get("intent") == "outdoor_space_permit_check":
        return {
            "currentStage": "outdoor_space_detail_screening",
            "stages": [
                {"id": "intent_classification", "label": "민원 목적 분류", "status": "done", "outputs": ["외부 테이블/테라스 사용 목적"]},
                {"id": "outdoor_space_detail_screening", "label": "도로점용/외부공간 1차 분류", "status": "waiting_for_input", "requiredInputs": ["address", "outdoor_location", "outdoor_area"], "outputs": ["도로점용 확인 필요성", "사용권한 확인 항목"]},
                {"id": "department_guide", "label": "담당 부서 문의 가이드", "status": "after_detail_check", "outputs": ["도로관리/건축/위생 관련 부서", "문의 문장"]},
            ],
            "boundary": {
                "serviceIntentRole": "사용자 목적이 창업인지, 외부공간 사용인지 먼저 분류합니다.",
                "canJudgeNow": ["외부공간 사용 민원으로 분기", "도로점용/사용권한 확인 필요성 안내"],
                "needsMoreInfo": ["사업장 주소", "보도/도로/사유지 여부", "테이블 수", "사용 면적"],
            },
        }
    if slots.get("intent") == "takeover_history_check":
        address_ready = slots["address"]["quality"] == "full"
        return {
            "currentStage": "same_place_lookup_ready" if address_ready else "same_place_lookup_input",
            "stages": [
                {"id": "intent_classification", "label": "민원 목적 분류", "status": "done", "outputs": ["기존 업소 인수/동일 장소 이력 확인 목적"]},
                {"id": "same_place_lookup", "label": "동일 장소 인허가 이력 조회", "status": "ready" if address_ready else "waiting_for_input", "requiredInputs": [] if address_ready else ["detailed_address"], "outputs": ["기존 업소 존재 여부", "동일 업종 여부", "행정처분 이력 후보"]},
                {"id": "department_guide", "label": "담당 부서 확인", "status": "after_lookup", "outputs": ["행정처분 승계/영업신고 영향 문의 문장", "위생과 또는 인허가 담당 부서"]},
            ],
            "boundary": {
                "serviceIntentRole": "사용자 목적이 신규 창업 가능성인지, 기존 업소 이력 확인인지 먼저 분류합니다.",
                "canJudgeNow": ["기존 업소 인수/행정처분 이력 확인 시나리오로 분기", "조회에 필요한 입력 안내"],
                "needsMoreInfo": ["상세주소", "인수하려는 업종", "기존 상호 또는 영업신고 정보가 있으면 추가"],
            },
        }
    if slots.get("intent") == "building_use_check":
        address_ready = slots["address"]["quality"] == "full"
        return {
            "currentStage": "building_ledger_ready" if address_ready else "building_ledger_input",
            "stages": [
                {"id": "intent_classification", "label": "민원 목적 분류", "status": "done", "outputs": ["건축물 용도/위반건축물 확인 목적"]},
                {"id": "building_ledger_lookup", "label": "건축물대장 조회", "status": "ready" if address_ready else "waiting_for_input", "requiredInputs": [] if address_ready else ["detailed_address"], "outputs": ["주용도", "층별 용도", "전유부/호실 면적", "위반건축물 여부"]},
                {"id": "business_use_match", "label": "희망 업종과 건축물 용도 대조", "status": "after_lookup", "outputs": ["휴게음식점/일반음식점/제과점 가능성", "불확실하면 담당 부서 문의 문장"]},
            ],
            "boundary": {
                "serviceIntentRole": "사용자 목적이 서류 안내인지, 건축물대장 기반 가능성 확인인지 먼저 분류합니다.",
                "canJudgeNow": ["건축물대장 조회 필요 시나리오로 분기", "조회 결과에서 볼 항목 안내"],
                "needsMoreInfo": ["상세주소", "층/호수", "확인하려는 업종"],
            },
        }
    if slots.get("intent") == "document_readiness_check":
        return {
            "currentStage": "document_checklist",
            "stages": [
                {"id": "intent_classification", "label": "민원 목적 분류", "status": "done", "outputs": ["서류 준비상태/제출 순서 확인 목적"]},
                {"id": "document_checklist", "label": "준비된 서류와 부족 서류 정리", "status": "waiting_for_input", "requiredInputs": ["prepared_documents", "target_business_type_if_unknown"], "outputs": ["현재 준비상태", "남은 서류", "영업신고 전/후 순서"]},
                {"id": "submission_order", "label": "제출 순서 안내", "status": "after_document_check", "outputs": ["영업신고증 발급", "사업자등록증 발급", "부서 문의 문장"]},
            ],
            "boundary": {
                "serviceIntentRole": "사용자 목적이 업종 가능성 판단인지, 서류 준비상태 점검인지 먼저 분류합니다.",
                "canJudgeNow": ["서류 준비상태 점검 시나리오로 분기", "공통 제출 순서 안내", "이미 준비된 서류와 모르는 서류 분리"],
                "needsMoreInfo": ["확인할 업종", "현재 준비된 서류", "주소/층/면적: 소방 또는 건축물 조건까지 보려면 필요"],
            },
        }

    address_ready = slots["address"]["quality"] == "full"
    return {
        "currentStage": "building_property_check_ready" if address_ready else "preliminary_route_screening",
        "stages": [
            {
                "id": "slot_filling",
                "label": "자연어 조건 추출",
                "status": "done",
                "outputs": ["업종 후보", "지역 힌트", "면적", "간판/외부공간 여부"],
            },
            {
                "id": "preliminary_route_screening",
                "label": "1차 업종/행위 사전진단",
                "status": "done",
                "outputs": ["휴게음식점/일반음식점 후보", "주류 분기", "300㎡ 기준", "간판/도로점용 이슈"],
            },
            {
                "id": "building_property_check",
                "label": "건물/입지 검증",
                "status": "ready" if address_ready else "waiting_for_input",
                "requiredInputs": [] if address_ready else ["detailed_address"],
                "outputs": ["건축물대장 용도", "위반건축물 여부", "기존 업소 행정처분 이력"],
            },
            {
                "id": "submission_readiness",
                "label": "서류/부서/제출 순서 확정",
                "status": "after_building_check",
                "outputs": ["필요 서류", "담당 부서", "문의 문장", "진행 순서"],
            },
        ],
        "boundary": {
            "detailedAddressRole": "최종 판단 자체가 아니라 건물/입지 검증을 위한 입력입니다.",
            "canJudgeWithoutDetailedAddress": ["업종 후보", "주류 판매 조합", "면적 300㎡ 기준", "간판/외부공간 확인 필요성", "공통 서류"],
            "cannotJudgeWithoutDetailedAddress": ["건축물 용도 적합성", "위반건축물 여부", "동일 장소 기존 업소 이력", "건물 기준 최종 가능성"],
        },
    }


def build_api_plan(slots: dict[str, Any]) -> dict[str, Any]:
    if slots.get("intent") == "signboard_permit_check":
        return {
            "serviceIntent": "signboard_permit_check",
            "addressForApi": slots["address"].get("lookupAddress") or "",
            "regionHint": slots["address"].get("raw") or "",
            "canRunPreliminaryDiagnosis": True,
            "canUseRegionHintForDepartmentGuide": bool(slots["address"].get("raw")),
            "canRunAddressApi": slots["address"]["quality"] == "full",
            "canRunBuildingLedgerApi": False,
            "canRunPastBusinessLookup": False,
            "canRunBuildingDecision": False,
            "canRunDecisionEngine": False,
            "skipReason": "간판 인허가 흐름입니다. 건축물대장 기반 음식점 판단은 호출하지 않습니다.",
        }
    if slots.get("intent") == "outdoor_space_permit_check":
        return {
            "serviceIntent": "outdoor_space_permit_check",
            "addressForApi": slots["address"].get("lookupAddress") or "",
            "regionHint": slots["address"].get("raw") or "",
            "canRunPreliminaryDiagnosis": True,
            "canUseRegionHintForDepartmentGuide": bool(slots["address"].get("raw")),
            "canRunAddressApi": slots["address"]["quality"] == "full",
            "canRunBuildingLedgerApi": False,
            "canRunPastBusinessLookup": False,
            "canRunBuildingDecision": False,
            "canRunDecisionEngine": False,
            "skipReason": "외부공간/도로점용 확인 흐름입니다. 건축물대장 기반 음식점 판단은 호출하지 않습니다.",
        }
    if slots.get("intent") == "takeover_history_check":
        address_ready = slots["address"]["quality"] == "full"
        return {
            "serviceIntent": "takeover_history_check",
            "addressForApi": slots["address"].get("lookupAddress") or "",
            "regionHint": slots["address"].get("raw") or "",
            "canRunPreliminaryDiagnosis": True,
            "canRunPastBusinessLookup": address_ready,
            "canRunBuildingLedgerApi": False,
            "canRunDecisionEngine": False,
            "skipReason": "" if address_ready else "상세주소가 없어 동일 장소 인허가 이력 조회를 보류합니다.",
        }
    if slots.get("intent") == "building_use_check":
        address_ready = slots["address"]["quality"] == "full"
        return {
            "serviceIntent": "building_use_check",
            "addressForApi": slots["address"].get("lookupAddress") or "",
            "regionHint": slots["address"].get("raw") or "",
            "canRunPreliminaryDiagnosis": True,
            "canRunBuildingLedgerApi": address_ready,
            "canRunAddressApi": address_ready,
            "canRunDecisionEngine": False,
            "skipReason": "" if address_ready else "상세주소가 없어 건축물대장 조회를 보류합니다.",
        }
    if slots.get("intent") == "document_readiness_check":
        address_ready = slots["address"]["quality"] == "full"
        return {
            "serviceIntent": "document_readiness_check",
            "addressForApi": slots["address"].get("lookupAddress") or "",
            "regionHint": slots["address"].get("raw") or "",
            "canRunPreliminaryDiagnosis": True,
            "canRunAddressApi": address_ready,
            "canRunBuildingLedgerApi": address_ready,
            "canRunPastBusinessLookup": False,
            "canRunBuildingDecision": False,
            "canRunDecisionEngine": False,
            "skipReason": "" if address_ready else "서류 준비상태 점검은 먼저 가능하고, 주소가 있으면 소방/건축물 조건 확인까지 확장합니다.",
        }

    address_ready = slots["address"]["quality"] == "full"
    has_region_hint = slots["address"].get("hasDistrict") or bool(slots["address"].get("raw"))
    return {
        "addressForApi": slots["address"].get("lookupAddress") or "",
        "regionHint": slots["address"].get("raw") or "",
        "canRunPreliminaryDiagnosis": True,
        "canUseRegionHintForDepartmentGuide": bool(has_region_hint),
        "canRunAddressApi": address_ready,
        "canRunBuildingLedgerApi": address_ready,
        "canRunPastBusinessLookup": address_ready,
        "canRunBuildingDecision": address_ready,
        "canRunDecisionEngine": address_ready,
        "areaCanBeInferredByApi": address_ready,
        "areaInferencePolicy": [
            "1순위: 사용자가 입력한 영업장 면적 또는 임대차계약서 면적",
            "2순위: 건축물대장 전유부/호실 면적",
            "3순위: 층별개요 면적",
            "4순위: 같은 주소 기존 인허가 데이터 면적",
            "없으면 사용자 입력 필요",
        ],
        "skipReason": "" if address_ready else "상세주소가 없어 건물/입지 검증용 API 호출만 보류합니다. 1차 사전진단은 가능합니다.",
    }


def summarize_current_state(slots: dict[str, Any], api_plan: dict[str, Any]) -> dict[str, Any]:
    if slots.get("intent") == "signboard_permit_check":
        return {
            "possibleNow": [
                "간판 설치/변경 민원으로 분류",
                "옥외광고물 표시허가 또는 신고 후보 안내",
                "공통 구비서류 안내",
                "입력된 지역 기준 담당 부서 후보 연결",
            ],
            "blockedOrUncertain": [
                "간판 종류별 허가/신고 구분",
                "간판 크기/설치 높이 기준",
                "건물 또는 대지 사용 승낙 여부",
            ],
        }
    if slots.get("intent") == "outdoor_space_permit_check":
        return {
            "possibleNow": [
                "외부 테이블/테라스 사용 민원으로 분류",
                "도로점용 또는 사유지 사용권한 확인 필요성 안내",
                "공통 확인 서류 안내",
            ],
            "blockedOrUncertain": [
                "외부공간이 보도/도로인지 사유지인지",
                "사용 면적과 테이블 수",
                "소유자/관리인 승낙 여부",
            ],
        }
    if slots.get("intent") == "takeover_history_check":
        return {
            "possibleNow": ["기존 업소 인수/동일 장소 이력 확인 시나리오로 분류", "필요 조회 항목 안내"],
            "blockedOrUncertain": ["상세주소 기준 기존 업소 이력 조회", "행정처분 영향 여부 담당 부서 확인"],
        }
    if slots.get("intent") == "building_use_check":
        return {
            "possibleNow": ["건축물 용도/위반건축물 확인 시나리오로 분류", "건축물대장 조회 필요 항목 안내"],
            "blockedOrUncertain": ["상세주소 기준 건축물대장 조회", "희망 업종별 용도 기준 대조"],
        }
    if slots.get("intent") == "document_readiness_check":
        prepared_docs = [
            label
            for key, label in [
                ("leaseContract", "임대차계약서"),
                ("hygieneTraining", "위생교육 수료증"),
                ("healthCertificate", "건강진단결과서"),
                ("fireCertificate", "소방완비증명서"),
                ("businessPermitReport", "영업신고증"),
                ("businessRegistration", "사업자등록증"),
            ]
            if slots["documents"].get(key) == "prepared"
        ]
        return {
            "possibleNow": [
                "서류 준비상태 점검 시나리오로 분류",
                "영업신고증 발급 후 사업자등록증 발급 순서 안내",
                f"준비 완료로 인식한 서류: {', '.join(prepared_docs)}" if prepared_docs else "준비 완료로 확정된 서류는 아직 없음",
            ],
            "blockedOrUncertain": [
                "업종별 위생교육 기관",
                "소방완비증명서 해당 여부: 층/면적 기준 필요",
                "건축물 용도까지 함께 보려면 상세주소 필요",
            ],
        }

    possible_now = [
        "업종 후보 추출",
        "주류 판매 여부에 따른 경로 분기" if slots["business"]["liquorSales"] is not None else "주류 여부 질문 생성",
        "공통 영업신고 서류 체크리스트 생성",
    ]
    if api_plan.get("canUseRegionHintForDepartmentGuide"):
        possible_now.append("입력된 지역 기준 담당 부서 후보 연결")
    blocked_now = []
    if not api_plan["canRunBuildingLedgerApi"]:
        blocked_now.extend(["건물/입지 검증: 건축물대장 용도 확인", "건물/입지 검증: 위반건축물 여부 확인", "건물/입지 검증: 기존 업소 행정처분 이력 확인"])
    if slots["space"]["areaM2"] is None:
        blocked_now.extend(["300㎡ 기준 확정", "소방완비증명서 면적 기준 확정"])
    return {
        "possibleNow": possible_now,
        "blockedOrUncertain": blocked_now,
    }


def run_decision_engine(slots: dict[str, Any], api_plan: dict[str, Any]) -> dict[str, Any]:
    if not api_plan["canRunDecisionEngine"]:
        return {
            "status": "skipped",
            "reason": api_plan["skipReason"],
        }
    if build_all_combinations is None:
        return {
            "status": "error",
            "reason": "decision_engine_import_failed",
            "message": DECISION_ENGINE_IMPORT_ERROR,
        }

    try:
        result = build_all_combinations(
            address=slots["address"]["full"],
            area_m2=slots["space"]["areaM2"],
        )
    except SystemExit as exc:
        return {
            "status": "error",
            "reason": "decision_engine_system_exit",
            "message": str(exc),
        }
    except Exception as exc:
        return {
            "status": "error",
            "reason": "decision_engine_failed",
            "message": f"{type(exc).__name__}: {exc}",
        }

    return {
        "status": "ok",
        "mode": "all_combinations",
        "result": result,
    }


def summarize_building_profile(profile: dict[str, Any]) -> dict[str, Any]:
    records = profile.get("records") or {}
    normalized = profile.get("normalized") or {}
    return {
        "status": profile.get("status"),
        "roadAddr": normalized.get("roadAddr") or normalized.get("rnAdres") or "",
        "jibunAddr": normalized.get("jibunAddr") or normalized.get("lnmAdres") or "",
        "buildingParams": profile.get("buildingParams"),
        "summary": profile.get("summary"),
        "recordCounts": {
            "title": len(records.get("title") or []),
            "floor": len(records.get("floor") or []),
            "unit": len(records.get("unit") or []),
            "landZone": len(records.get("land_zone") or []),
        },
    }


def summarize_past_businesses(past: dict[str, Any]) -> dict[str, Any]:
    matches = past.get("matches") or []
    return {
        "status": past.get("status", "ok"),
        "index": past.get("index") or "",
        "queryAddress": past.get("queryAddress") or "",
        "addressKeys": past.get("addressKeys") or [],
        "count": len(matches),
        "sample": [
            {
                "businessName": item.get("business_name") or item.get("bplcNm") or "",
                "businessType": item.get("canonical_business_type") or item.get("business_type") or "",
                "licenseDate": item.get("license_date") or "",
                "status": item.get("status") or item.get("dtlStateNm") or "",
                "detailStatus": item.get("detail_status") or "",
                "areaM2": item.get("area_m2"),
                "address": item.get("road_address") or item.get("lot_address") or item.get("address") or item.get("rdnWhlAddr") or item.get("siteWhlAddr") or "",
            }
            for item in matches[:5]
        ],
    }


def summarize_combined_past_businesses(all_past: dict[str, Any], same_or_similar_past: dict[str, Any] | None = None) -> dict[str, Any]:
    all_summary = summarize_past_businesses(all_past)
    same_summary = summarize_past_businesses(same_or_similar_past or {"status": "skipped", "matches": []})
    status = all_summary.get("status") or same_summary.get("status") or "ok"
    if status == "ok":
        if all_summary.get("count", 0) > 0:
            label = "matched"
        else:
            label = "no_match"
    else:
        label = status
    return {
        **all_summary,
        "status": status,
        "label": label,
        "allCount": all_summary.get("count", 0),
        "sameOrSimilarCount": same_summary.get("count", 0),
        "sameOrSimilarSample": same_summary.get("sample", []),
        "sameOrSimilarStatus": same_summary.get("status"),
    }


def infer_past_lookup_business_type(slots: dict[str, Any]) -> str:
    business = slots.get("business") or {}
    candidates = business.get("candidateTypes") or []
    if candidates:
        return str(candidates[0] or "")

    text = " ".join(
        str(value or "")
        for value in [
            business.get("rawText"),
            business.get("concept"),
            business.get("requestedType"),
            *(business.get("salesItems") or []),
        ]
    )
    compact = re.sub(r"\s+", "", text).lower()
    if any(token in compact for token in ["일반음식", "일반음식점", "고깃집", "고기집", "삼겹살", "식당", "주점", "호프"]):
        return BUSINESS_TYPES["general_restaurant"]
    if any(token in compact for token in ["카페", "커피", "디저트", "음료", "휴게음식", "휴게음식점"]):
        return BUSINESS_TYPES["cafe"]
    if any(token in compact for token in ["제과", "제과점", "베이커리", "빵집"]):
        return BUSINESS_TYPES["bakery"]
    return ""


def similar_business_types_for_lookup(business_type: str) -> list[str]:
    food_types = [
        BUSINESS_TYPES["general_restaurant"],
        BUSINESS_TYPES["cafe"],
        BUSINESS_TYPES["bakery"],
    ]
    if business_type in food_types:
        return [business_type, *[item for item in food_types if item != business_type]]
    return [business_type] if business_type else []


def query_same_or_similar_past_businesses(index: Path, address: str, limit: int, business_type: str) -> dict[str, Any] | None:
    lookup_types = similar_business_types_for_lookup(business_type)
    if not lookup_types:
        return None

    merged_matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    last_result: dict[str, Any] | None = None
    for lookup_type in lookup_types:
        current = query_past_businesses(index, address, limit, lookup_type)
        last_result = current
        if current.get("status") != "ok":
            return current
        for item in current.get("matches") or []:
            key = (
                str(item.get("license_no") or ""),
                str(item.get("business_name") or ""),
                str(item.get("road_address") or item.get("lot_address") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged_matches.append(item)
            if len(merged_matches) >= limit:
                break
        if len(merged_matches) >= limit:
            break

    return {
        **(last_result or {}),
        "status": "ok",
        "queryAddress": address,
        "similarBusinessTypes": lookup_types,
        "matches": merged_matches,
    }


def run_external_checks(slots: dict[str, Any], api_plan: dict[str, Any]) -> dict[str, Any]:
    if EXTERNAL_CHECK_IMPORT_ERROR:
        return {"status": "error", "reason": "external_check_import_failed", "message": EXTERNAL_CHECK_IMPORT_ERROR}

    address = api_plan.get("addressForApi") or slots.get("address", {}).get("lookupAddress") or ""
    result: dict[str, Any] = {
        "status": "ok",
        "addressForApi": address,
        "buildingLedger": {"status": "skipped", "reason": "not_required_or_address_missing"},
        "pastBusinessLookup": {"status": "skipped", "reason": "not_required_or_address_missing"},
    }

    if api_plan.get("canRunBuildingLedgerApi") and address and build_building_profile is not None:
        try:
            result["buildingLedger"] = summarize_building_profile(build_building_profile(address))
        except SystemExit as exc:
            result["buildingLedger"] = {"status": "error", "reason": "system_exit", "message": str(exc)}
        except Exception as exc:
            result["buildingLedger"] = {"status": "error", "reason": "api_failed", "message": f"{type(exc).__name__}: {exc}"}

    if api_plan.get("canRunPastBusinessLookup") and address and query_past_businesses is not None and DEFAULT_INDEX is not None:
        business_type = infer_past_lookup_business_type(slots)
        try:
            all_past = query_past_businesses(DEFAULT_INDEX, address, 10, "")
            same_or_similar_past = query_same_or_similar_past_businesses(DEFAULT_INDEX, address, 10, business_type)
            result["pastBusinessLookup"] = summarize_combined_past_businesses(all_past, same_or_similar_past)
        except Exception as exc:
            result["pastBusinessLookup"] = {"status": "error", "reason": "lookup_failed", "message": f"{type(exc).__name__}: {exc}"}

    return result


def build_intake_result(
    text: str,
    run_decision: bool = True,
    slot_provider: str = "rule",
    fallback_to_rule: bool = True,
    judgement_provider: str = "rule",
    judgement_fallback_to_rule: bool = True,
    inquiry_provider: str = "rule",
    inquiry_fallback_to_rule: bool = True,
) -> dict[str, Any]:
    normalized = normalize_space(text)
    slot_filling = fill_slots(normalized, provider=slot_provider, fallback_to_rule=fallback_to_rule)
    slots = contract_to_pipeline_slots(slot_filling["contract"], normalized)
    missing_info = build_missing_info(slots)
    api_plan = build_api_plan(slots)
    preliminary_diagnosis = build_preliminary_diagnosis(slots)
    scenario_plan = build_scenario_plan(slots)
    result = {
        "status": "ok",
        "inputText": normalized,
        "slotFilling": slot_filling,
        "scenarioPlan": scenario_plan,
        "slots": slots,
        "preliminaryDiagnosis": preliminary_diagnosis,
        "diagnosisFlow": build_diagnosis_flow(slots, api_plan),
        "missingInfo": missing_info,
        "apiPlan": api_plan,
        "currentState": summarize_current_state(slots, api_plan),
    }
    result["requirementGraph"] = build_requirement_graph(slots)
    if run_decision:
        result["externalChecks"] = run_external_checks(slots, api_plan)
        result["decisionEngine"] = run_decision_engine(slots, api_plan)
    result["aiJudgement"] = run_ai_judgement(
        result,
        provider=judgement_provider,
        fallback_to_rule=judgement_fallback_to_rule,
    )
    effective_inquiry_provider = inquiry_provider
    inquiry_policy = {
        "requestedProvider": inquiry_provider,
        "effectiveProvider": inquiry_provider,
        "deferredAi": False,
        "reason": "",
    }
    if (
        str(inquiry_provider).lower() in {"gms", "openai"}
        and result.get("missingInfo", {}).get("requiredNow")
    ):
        effective_inquiry_provider = "rule"
        inquiry_policy.update(
            {
                "effectiveProvider": "rule",
                "deferredAi": True,
                "reason": "required information is still missing, so the LLM inquiry script is deferred until the next run.",
            }
        )
    result["inquiryScriptPolicy"] = inquiry_policy
    result["inquiryPackage"] = build_inquiry_package(
        result,
        provider=effective_inquiry_provider,
        fallback_to_rule=inquiry_fallback_to_rule,
    )
    result["aiGuidance"] = build_ai_guidance_packet(result)
    return result


def write_json(data: dict[str, Any], output: Path | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HEOGAON natural-language intake pipeline.")
    parser.add_argument("--text", required=True, help="사용자 자연어 입력")
    parser.add_argument("--no-decision", action="store_true", help="slot filling과 질문 생성만 수행")
    parser.add_argument("--slot-provider", choices=["rule", "gms"], default="rule", help="slot filling provider. gms는 추후 실제 호출로 교체")
    parser.add_argument("--no-slot-fallback", action="store_true", help="gms 실패 시 rule provider로 fallback하지 않음")
    parser.add_argument("--judgement-provider", choices=["rule", "gms", "openai"], default="rule", help="final judgement provider. AI 실패 시 기본적으로 rule fallback")
    parser.add_argument("--no-judgement-fallback", action="store_true", help="AI judgement 실패 시 rule fallback하지 않음")
    parser.add_argument("--inquiry-provider", choices=["rule", "gms", "openai"], default="rule", help="inquiry script provider. AI 실패 시 기본적으로 rule fallback")
    parser.add_argument("--no-inquiry-fallback", action="store_true", help="inquiry script generation 실패 시 rule fallback하지 않음")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_intake_result(
        args.text,
        run_decision=not args.no_decision,
        slot_provider=args.slot_provider,
        fallback_to_rule=not args.no_slot_fallback,
        judgement_provider=args.judgement_provider,
        judgement_fallback_to_rule=not args.no_judgement_fallback,
        inquiry_provider=args.inquiry_provider,
        inquiry_fallback_to_rule=not args.no_inquiry_fallback,
    )
    write_json(result, args.output)


if __name__ == "__main__":
    main()
