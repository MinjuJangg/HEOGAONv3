"""서류 작성 가이드 빌더.

수집한 case 데이터(주소·면적·업종 등)를 정부24 신청 양식 항목에 매핑해
"이렇게 선택/입력하면 된다"는 가이드를 미리 채워서 만든다. 프론트는 이 구조를
그대로 렌더링하고 값만 복사할 수 있게 보여준다(= back interprets, front shows).

현재는 식품 영업 신고서 / 식품접객업 영업신고증 두 서류만 지원한다.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.slot_utils import slot_value

GOV24_FOOD_REPORT_URL = (
    "https://www.gov.kr/mw/AA020InfoCappView.do"
    "?CappBizCD=14600000021&HighCtgCD=A09006&tp_seq=02"
)


def build_writing_guide(case: dict[str, Any], title: str) -> dict[str, Any] | None:
    """대상 서류면 작성 가이드를 만들고, 아니면 None."""
    normalized = _normalize(title)
    is_report = any(token in normalized for token in ["영업신고서", "식품영업신고", "영업신고증", "식품접객업"])
    if not is_report:
        return None
    return _food_business_report_guide(case, normalized)


def _food_business_report_guide(case: dict[str, Any], normalized_title: str) -> dict[str, Any]:
    is_certificate = "영업신고증" in normalized_title

    address = _readable_address(case)
    inner_area = _area_text(slot_value(case, "area"))
    outer_area = _area_text(slot_value(case, "outdoor_area"))
    business_kind, _ = _business_kind(case)

    # 선택 항목은 정부24 양식 구조(상위 항목 > 세부 항목) 기준의 group을 함께 내려준다.
    select_items: list[dict[str, Any]] = [
        {"label": "영업의 종류", "group": "신고사항", "choose": business_kind},
        {"label": "식품용수의 종류", "group": "신고사항", "choose": "수돗물"},
        {"label": "공유주방의 사용 여부", "group": "신고사항", "choose": "미해당"},
        {"label": "공동조리장 이용 여부", "group": "신고사항", "choose": "미해당"},
        {"label": "행정정보 공동이용 동의", "group": "행정정보 공동이용 동의서", "choose": "동의"},
    ]

    fill_items: list[dict[str, Any]] = [
        {"label": "영업장의 소재지", "value": address, "filled": bool(address), "hint": "사업장 주소"},
        {"label": "영업장 면적(건물 내부)", "value": inner_area, "filled": bool(inner_area), "hint": "㎡ 단위"},
    ]
    if outer_area:
        fill_items.append(
            {"label": "영업장 면적(건물 외부)", "value": outer_area, "filled": True, "hint": "외부 테이블 등 사용 시"}
        )
    fill_items.extend(
        [
            {"label": "명칭(상호)", "value": "", "filled": False, "hint": "가게 상호명 직접 입력"},
            {"label": "신고인 성명(대표자)", "value": "", "filled": False, "hint": "대표자 본인 이름"},
            {"label": "주민(법인)등록번호", "value": "", "filled": False, "hint": "직접 입력"},
            {"label": "집 주소 / 전화번호", "value": "", "filled": False, "hint": "신고인 연락처 직접 입력"},
        ]
    )

    intro = (
        "‘식품 영업 신고서’를 정부24에서 접수하면 검토 후 영업신고증이 발급돼요. "
        "별도 작성 양식은 없고, 아래 신고서 작성 내용을 그대로 따르면 됩니다."
        if is_certificate
        else "정부24 ‘식품영업신고’에서 아래처럼 선택·입력하면 돼요. 미리 채워둔 값은 복사해서 붙여넣으세요."
    )

    return {
        "title": "식품 영업 신고서 작성 가이드",
        "intro": intro,
        "applyUrl": GOV24_FOOD_REPORT_URL,
        "applyLabel": "정부24 식품영업신고 바로가기",
        "sections": [
            {"title": "이렇게 선택하세요", "type": "select", "items": select_items},
            {"title": "이렇게 입력하세요", "type": "fill", "items": fill_items},
        ],
        "attachments": [
            "위생교육 수료증",
            "건강진단결과서(보건증)",
            "임대차계약서 등 영업장 사용 권한 증빙",
            "소방 안전시설등 완비증명서(다중이용업 해당 시)",
        ],
        "footnote": "성명·주민등록번호 등 개인정보 항목은 본인이 직접 입력해야 해요.",
    }


def _readable_address(case: dict[str, Any]) -> str:
    slot = (case.get("slots") or {}).get("exact_address") or {}
    address = slot.get("userText") or slot.get("value")
    floor = slot_value(case, "floor_unit")
    if address:
        text = str(address).strip()
        if floor and str(floor).strip() and str(floor) not in text:
            text = f"{text} {str(floor).strip()}"
        return text

    summary = ((case.get("minjuIntake") or {}).get("summary") or {}) or (
        (case.get("minjuDraft") or {}).get("summary") or {}
    )
    address_info = (summary.get("slots") or {}).get("address") or {}
    return str(address_info.get("full") or address_info.get("lookupAddress") or address_info.get("raw") or "").strip()


def _area_text(value: Any) -> str:
    if value in (None, "", "unknown"):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if re.search(r"(㎡|m2|m²|제곱|평)", text):
        return text
    return f"{text}㎡"


def _business_kind(case: dict[str, Any]) -> tuple[str, str]:
    business = str(slot_value(case, "business_activity") or "")
    raw = f"{business} {case.get('rawInput') or ''}"
    if re.search(r"제과|베이커리|빵집|빵\b|케이크|디저트", raw):
        return "제과점영업", "빵·케이크 등 제과 중심이면 제과점영업"
    if re.search(r"카페|커피|음료|차\b|티\b", raw) and slot_value(case, "on_site_consumption") is not True:
        return "휴게음식점영업", "주류 없이 음료·간단한 음식 위주(객석 취식)면 휴게음식점영업"
    return "일반음식점영업", "음식 조리·판매(객석 취식)면 일반음식점영업. 카페·제과는 휴게음식점/제과점도 검토"


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()
