from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CSV_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")

SEOUL_SIGUNGU_CODES = {
    "종로구": "11110",
    "중구": "11140",
    "용산구": "11170",
    "성동구": "11200",
    "광진구": "11215",
    "동대문구": "11230",
    "중랑구": "11260",
    "성북구": "11290",
    "강북구": "11305",
    "도봉구": "11320",
    "노원구": "11350",
    "은평구": "11380",
    "서대문구": "11410",
    "마포구": "11440",
    "양천구": "11470",
    "강서구": "11500",
    "구로구": "11530",
    "금천구": "11545",
    "영등포구": "11560",
    "동작구": "11590",
    "관악구": "11620",
    "서초구": "11650",
    "강남구": "11680",
    "송파구": "11710",
    "강동구": "11740",
}


BUSINESS_TYPE_BY_FILE_TOKEN = {
    "일반음식점": "일반음식점영업",
    "휴게음식점": "휴게음식점영업",
    "제과점영업": "제과점영업",
    "즉석판매제조가공업": "즉석판매제조·가공업",
    "건강기능식품일반판매업": "건강기능식품일반판매업",
    "식품판매업기타": "기타식품판매업",
    "통신판매업": "통신판매업",
    "옥외광고업": "옥외광고업",
    "담배소매업": "담배소매업",
    "미용업": "미용업",
    "세탁업": "세탁업",
    "노래연습장업": "노래연습장업",
    "체력단련장업": "체력단련장업",
    "건물위생관리업": "건물위생관리업",
    "세차장정보": "세차장",
}


FIELD_CANDIDATES = {
    "license_no": ["관리번호", "인허가번호", "허가번호"],
    "license_date": ["인허가일자", "신고일자", "등록일자", "지정일자"],
    "cancel_date": ["인허가취소일자"],
    "status": ["영업상태명", "상세영업상태명", "상태명"],
    "detail_status": ["상세영업상태명"],
    "status_code": ["영업상태코드", "상세영업상태코드"],
    "close_date": ["폐업일자"],
    "business_name": ["사업장명", "업소명", "상호명"],
    "subtype": ["업태구분명", "위생업태명", "사업장업종명", "문화체육업종명", "민원종류명", "영업내용"],
    "area_m2": ["소재지면적", "시설총규모", "시설면적", "영업장면적", "건축물연면적"],
    "road_address": ["도로명주소", "소재지도로명주소", "소재지도로명"],
    "lot_address": ["지번주소", "소재지지번주소", "소재지전체주소", "소재지지번"],
    "district": ["시군구명", "시군구"],
    "phone": ["전화번호", "세차장전화번호"],
    "x": ["좌표정보(X)", "X"],
    "y": ["좌표정보(Y)", "Y"],
}


def choose_csv_encoding(path: Path) -> str:
    sample = path.read_bytes()[:1024 * 1024]
    for encoding in CSV_ENCODINGS:
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return CSV_ENCODINGS[-1]


def first_value(row: dict[str, str], candidates: list[str]) -> str:
    for key in candidates:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def strip_unit_detail(address: str) -> str:
    text = normalize_space(address)
    text = re.split(r"[,，]", text, maxsplit=1)[0]
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_address_key(address: str) -> str:
    text = strip_unit_detail(address)
    text = text.replace("서울시", "서울특별시")
    text = re.sub(r"(서울특별시|서울)", "", text)
    text = re.sub(r"[^0-9A-Za-z가-힣]", "", text)
    return text.lower()


def extract_district(address: str) -> str:
    match = re.search(r"([가-힣]+구)", address or "")
    return match.group(1) if match else ""


def extract_neighborhood(address: str) -> str:
    match = re.search(r"([가-힣]+동)", address or "")
    return match.group(1) if match else ""


def canonical_business_type(file_name: str, row: dict[str, str] | None = None) -> str:
    row = row or {}
    subtype = first_value(row, FIELD_CANDIDATES["subtype"])
    candidates = [subtype, file_name]
    for text in candidates:
        compact = re.sub(r"[\s_·ㆍ-]+", "", str(text or ""))
        for token, canonical in BUSINESS_TYPE_BY_FILE_TOKEN.items():
            if re.sub(r"[\s_·ㆍ-]+", "", token) in compact:
                return canonical
    return Path(file_name).stem.replace("_서울특별시", "")


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def seoul_sigungu_code(address: str, district: str = "") -> str:
    district = district or extract_district(address)
    return SEOUL_SIGUNGU_CODES.get(district, "")

