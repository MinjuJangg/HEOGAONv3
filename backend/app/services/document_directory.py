from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.services.slot_utils import slot_value


REPO_ROOT = Path(__file__).resolve().parents[3]
DOCUMENT_DB = REPO_ROOT / "heogaon" / "document_issue_guide" / "document_issue_guide.sqlite"
DEPARTMENT_DB = REPO_ROOT / "heogaon" / "department_mapping" / "seoul_department_mapping.sqlite"


DOCUMENT_PROCESSING_PROFILE: dict[str, str] = {
    "building_ledger_result": "building_register",
    "building-ledger": "building_register",
    "same_place_history_result": "same_place_history_lookup",
    "food_business_report": "food_business_report",
    "food-business-report": "food_business_report",
    "hygiene_training": "hygiene_training",
    "hygiene-education": "hygiene_training",
    "health_certificate": "health_certificate",
    "health-check": "health_certificate",
    "lease_contract": "applicant_prepared_document",
    "id_card": "applicant_prepared_document",
    "fire_safety_certificate": "fire_safety_completion",
    "fire-safety": "fire_safety_completion",
    "lpg_completion_certificate": "lpg_completion",
    "lpg-certificate": "lpg_completion",
    "business_registration": "business_registration",
    "business-registration": "business_registration",
    "signboard_application": "outdoor_ad_report",
    "signage-report": "outdoor_ad_report",
    "signboard_owner_consent": "applicant_prepared_document",
    "signboard_photo_design": "applicant_prepared_document",
    "outdoor_space_materials": "road_occupation_permit",
    "road-occupation": "road_occupation_permit",
    "outdoor_owner_consent": "applicant_prepared_document",
}


PROCESSING_TITLE_RULES: list[tuple[list[str], str]] = [
    (["건축물대장", "건축물 용도", "위반건축물"], "building_register"),
    (["동일장소", "행정처분", "기존업소"], "same_place_history_lookup"),
    (["건강진단", "보건증"], "health_certificate"),
    (["위생교육"], "hygiene_training"),
    (["소방완비", "안전시설"], "fire_safety_completion"),
    (["액화석유가스", "LPG", "가스 완성", "완성검사"], "lpg_completion"),
    (["사업자등록"], "business_registration"),
    (["영업 신고서", "영업신고서", "영업신고증", "식품접객업"], "food_business_report"),
    (["사용승낙", "사용 승낙", "건물/대지"], "applicant_prepared_document"),
    (["원색도안", "설계도", "위치 사진", "위치사진"], "applicant_prepared_document"),
    (["임대차", "사용권한", "사용 권한", "신분증"], "applicant_prepared_document"),
    (["도로점용", "외부공간", "외부 공간", "보도", "위치도", "평면도"], "road_occupation_permit"),
    (["옥외광고", "간판"], "outdoor_ad_report"),
]


TASK_PROCESSING_PROFILE: dict[str, str] = {
    "food_business_report": "food_business_report",
    "fire_safety_completion": "fire_safety_completion",
    "business_registration": "business_registration",
    "outdoor_ad_report": "outdoor_ad_report",
    "road_occupation_permit": "road_occupation_permit",
    "building_register_issue": "building_register",
}


DEFAULT_PROCESSING_PROFILE: dict[str, str] = {
    "profile_id": "not_found",
    "processing_time_scope": "not_found",
    "processing_time_kind": "no_public_processing_time_found",
    "min_business_days": "",
    "max_business_days": "",
    "min_minutes": "",
    "max_minutes": "",
    "display_text": "확인 필요",
    "schedule_priority_rank": "90",
    "schedule_blocker_type": "unknown",
    "confidence": "low",
    "variance": "unknown",
    "source_authority": "",
    "source_url": "",
    "last_checked": "",
    "notes": "No official public processing time was matched for this document.",
}


TITLE_RULES: list[tuple[list[str], str, str]] = [
    (["지위승계", "승계 신고", "양도", "양수"], "영업자 지위승계", "food_business_report"),
    (["임대차", "사용권한", "사용 권한"], "임대차계약서 또는 시설사용계약서", "food_business_report"),
    (["신분증"], "신분증", "food_business_report"),
    (["위생교육"], "위생교육 수료증", "food_business_report"),
    (["건강진단", "보건증"], "건강진단결과서", "food_business_report"),
    (["소방완비", "안전시설"], "안전시설등 완비증명서", "food_business_report"),
    (["액화석유가스", "LPG", "가스 완성", "완성검사"], "액화석유가스 사용시설완성검사증명서", "food_business_report"),
    (["영업 신고서", "영업신고서"], "식품 영업 신고서", "food_business_report"),
    (["영업신고증"], "식품접객업 영업신고증", "business_registration"),
    (["사업자등록 신청서"], "사업자등록 신청서", "business_registration"),
    (["사업자등록"], "사업자등록증", "business_registration"),
    (["옥외광고", "간판", "원색도안"], "옥외광고물", "outdoor_ad_report"),
    (["도로점용", "외부공간", "외부 공간", "테이블"], "도로점용허가 신청서", "road_occupation_permit"),
]


ISSUER_TASK_RULES: list[tuple[list[str], str]] = [
    (["지위승계", "승계 신고"], "food_business_report"),
    (["영업신고증"], "food_business_report"),
    (["소방완비", "안전시설"], "fire_safety_completion"),
    (["액화석유가스", "LPG", "가스 완성", "완성검사"], "fire_safety_completion"),
    (["사업자등록"], "business_registration"),
    (["옥외광고", "간판", "원색도안"], "outdoor_ad_report"),
    (["도로점용", "외부공간", "외부 공간", "테이블"], "road_occupation_permit"),
]


ISSUER_LINK_RULES: list[tuple[list[str], str, str]] = [
    (
        ["건축물대장"],
        "정부24 건축물대장 발급",
        "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000098",
    ),
    (
        ["건강진단", "보건증"],
        "정부24 건강진단결과서(보건증) 발급",
        "https://www.gov.kr/portal/service/serviceInfo/135200000129",
    ),
    (
        ["위생교육"],
        "한국외식업중앙회 위생교육",
        "https://www.ifoodedu.or.kr/",
    ),
    (
        ["영업 신고서", "영업신고서", "영업신고증", "식품접객업"],
        "정부24 식품관련영업신고",
        "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=14600000021&HighCtgCD=A09006&tp_seq=02",
    ),
    (
        ["사업자등록"],
        "국세청 홈택스",
        "https://www.hometax.go.kr",
    ),
    (
        ["옥외광고", "간판"],
        "정부24 옥외광고물 표시허가(신고)",
        "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&HighCtgCD=A09006",
    ),
    (
        ["도로점용", "외부공간", "외부 공간", "테이블"],
        "정부24 도로점용허가",
        "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000209&HighCtgCD=A09006",
    ),
]


EVIDENCE_ONLY_URL_MARKERS = (
    "easylaw.go.kr",
    "law.go.kr/DRF",
)


APPLICANT_PREPARED_TITLE_TOKENS = (
    "임대차",
    "신분증",
    "사용권한",
    "사용 권한",
    "사용승낙",
    "사용 승낙",
    "원색도안",
    "설계도",
    "위치 사진",
    "위치사진",
)


def lookup_document_directory(case: dict[str, Any], title: str) -> dict[str, Any]:
    district = extract_district(case)
    term, submit_task_key = term_and_submit_task(title)
    guide = fetch_document_guide(term) if term else None

    guide_task_key = first_task_key((guide or {}).get("submit_to_local_task_key") or "")
    submit_task_key = submit_task_key or guide_task_key
    issuer_task_key = issuer_task_for(title)
    processing_time = lookup_processing_time(title, submit_task_key=submit_task_key)

    submit_department = fetch_department(district, submit_task_key)
    issuer_department = fetch_department(district, issuer_task_key)

    issuer = (guide or {}).get("issue_or_prepare_place") or ""
    if issuer_department and should_use_department_issuer(title, issuer):
        issuer = format_department(issuer_department, district)

    submit_to = ""
    if submit_department:
        submit_to = format_department(submit_department, district)
    else:
        submit_to = (guide or {}).get("submit_to") or ""

    issuer_link = issuer_link_for(title)
    issuer_url = issuer_link.get("url", "")
    issuer_label = issuer_link.get("label", "")
    if not issuer_url and issuer_department and (issuer_department.get("source_url") or ""):
        issuer_url = str(issuer_department.get("source_url") or "")
        issuer_label = str(issuer_department.get("source_title") or "발급처 안내")
    elif not issuer_url and guide and guide_source_is_actionable(guide, title):
        issuer_url = str(guide.get("source_url") or "")
        issuer_label = str(guide.get("source_title") or "발급/준비 안내")

    submit_map_url = department_map_url(submit_department)
    submit_url = submit_map_url or str((submit_department or {}).get("source_url") or "")
    submit_label = "지도에서 보기" if submit_map_url else ("위치/부서 확인" if submit_url else "제출처 안내")

    official_links = unique_links(
        [
            {
                "label": issuer_label or "발급/신청 안내",
                "url": issuer_url,
            },
            {"label": submit_label, "url": submit_url},
            guide_evidence_link(guide),
        ]
    )

    return {
        "district": district,
        "dbDocumentName": (guide or {}).get("document_name") or "",
        "issuer": issuer,
        "submitTo": submit_to,
        "submissionPhase": (guide or {}).get("when_needed") or "",
        "prerequisiteSummary": (guide or {}).get("prerequisite_summary") or "",
        "issueChannel": (guide or {}).get("issue_channel") or "",
        "issuerUrl": issuer_url,
        "issuerLinkLabel": issuer_label,
        "submitUrl": submit_url,
        "submitLinkLabel": submit_label if submit_url else "",
        "officialLinks": official_links,
        "processingTime": processing_time,
    }


def extract_district(case: dict[str, Any]) -> str:
    summary = ((case.get("minjuIntake") or {}).get("summary") or {}) or ((case.get("minjuDraft") or {}).get("summary") or {})
    summary_slots = summary.get("slots") or {}
    address = summary_slots.get("address") or {}
    slot_candidates = []
    if isinstance(case.get("slots"), dict):
        slot_candidates = [slot_value(case, "exact_address"), slot_value(case, "location")]
    candidates = [
        case.get("rawInput"),
        *slot_candidates,
        address.get("full"),
        address.get("lookupAddress"),
        address.get("raw"),
    ]
    for value in candidates:
        match = re.search(r"([가-힣]+구)", str(value or ""))
        if match:
            return match.group(1)

    package_district = ((summary.get("inquiryPackage") or {}).get("district") or "").strip()
    if package_district:
        return package_district
    return ""


def term_and_submit_task(title: str) -> tuple[str, str]:
    normalized = normalize(title)
    for tokens, term, task_key in TITLE_RULES:
        if any(normalize(token) in normalized for token in tokens):
            return term, task_key
    return title, ""


def issuer_task_for(title: str) -> str:
    normalized = normalize(title)
    for tokens, task_key in ISSUER_TASK_RULES:
        if any(normalize(token) in normalized for token in tokens):
            return task_key
    return ""


def fetch_document_guide(term: str) -> dict[str, Any] | None:
    if not term or not DOCUMENT_DB.exists():
        return None
    conn = sqlite3.connect(DOCUMENT_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT document_name,
                   issue_or_prepare_place,
                   issue_channel,
                   submit_to,
                   submit_to_local_task_key,
                   when_needed,
                   prerequisite_summary,
                   source_url,
                   source_title
            FROM all_document_issue_guide
            WHERE document_name LIKE ?
            ORDER BY
                CASE
                    WHEN document_name = ? THEN 0
                    WHEN document_name LIKE ? THEN 1
                    WHEN ? LIKE '%' || document_name || '%' THEN 2
                    ELSE 3
                END,
                CAST(graph_requirement_count AS INTEGER) DESC,
                CASE
                    WHEN source_url LIKE '%gov.kr%' THEN 0
                    WHEN source_url LIKE '%hometax.go.kr%' THEN 1
                    WHEN source_url LIKE '%law.go.kr/DRF%' THEN 4
                    WHEN source_url LIKE '%easylaw.go.kr%' THEN 3
                    ELSE 2
                END,
                length(document_name),
                document_name
            LIMIT 1
            """,
            (f"%{term}%", term, f"{term}%", term),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def issuer_link_for(title: str) -> dict[str, str]:
    normalized = normalize(title)
    for tokens, label, url in ISSUER_LINK_RULES:
        if any(normalize(token) in normalized for token in tokens):
            return {"label": label, "url": url}
    return {}


def guide_source_is_actionable(guide: dict[str, Any] | None, title: str) -> bool:
    url = str((guide or {}).get("source_url") or "")
    if is_applicant_prepared_title(title):
        return False
    if not url or any(marker in url for marker in EVIDENCE_ONLY_URL_MARKERS):
        return False
    return any(marker in url for marker in ("gov.kr", "hometax.go.kr"))


def is_applicant_prepared_title(title: str) -> bool:
    normalized = normalize(title)
    return any(normalize(token) in normalized for token in APPLICANT_PREPARED_TITLE_TOKENS)


def guide_evidence_link(guide: dict[str, Any] | None) -> dict[str, str]:
    url = str((guide or {}).get("source_url") or "")
    if not url or not any(marker in url for marker in EVIDENCE_ONLY_URL_MARKERS):
        return {}
    return {
        "label": "법령/안내 근거",
        "url": url,
    }


def fetch_department(district: str, task_key: str) -> dict[str, Any] | None:
    if not district or not task_key or not DEPARTMENT_DB.exists():
        return None
    conn = sqlite3.connect(DEPARTMENT_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT district_name,
                   local_task_key,
                   local_task_label,
                   actual_department_name,
                   actual_team_name,
                   phone,
                   source_url,
                   source_title,
                   office_name,
                   office_address,
                   office_location_source_url,
                   office_location_source_title
            FROM department_mapping
            WHERE district_name = ? AND local_task_key = ?
            LIMIT 1
            """,
            (district, task_key),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


@lru_cache(maxsize=1)
def fetch_processing_profiles() -> dict[str, dict[str, str]]:
    if not DOCUMENT_DB.exists():
        return {"not_found": DEFAULT_PROCESSING_PROFILE}
    conn = sqlite3.connect(DOCUMENT_DB)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute("SELECT * FROM service_processing_times").fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()
    profiles = {str(row["profile_id"]): dict(row) for row in rows}
    profiles.setdefault("not_found", DEFAULT_PROCESSING_PROFILE)
    return profiles


def lookup_processing_time(
    title: str,
    document_id: str = "",
    submit_task_key: str = "",
) -> dict[str, Any]:
    profiles = fetch_processing_profiles()
    profile_id = processing_profile_id_for(title, document_id, submit_task_key)
    profile = profiles.get(profile_id) or profiles["not_found"]
    return normalize_processing_profile(profile)


def processing_profile_id_for(title: str, document_id: str = "", submit_task_key: str = "") -> str:
    doc_id = str(document_id or "").strip()
    if doc_id in DOCUMENT_PROCESSING_PROFILE:
        return DOCUMENT_PROCESSING_PROFILE[doc_id]
    normalized = normalize(title)
    for tokens, profile_id in PROCESSING_TITLE_RULES:
        if any(normalize(token) in normalized for token in tokens):
            return profile_id
    task_key = first_task_key(submit_task_key)
    if task_key in TASK_PROCESSING_PROFILE:
        return TASK_PROCESSING_PROFILE[task_key]
    return "not_found"


def normalize_processing_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profileId": str(profile.get("profile_id") or "not_found"),
        "scope": str(profile.get("processing_time_scope") or ""),
        "kind": str(profile.get("processing_time_kind") or ""),
        "minBusinessDays": int_or_zero(profile.get("min_business_days")),
        "maxBusinessDays": int_or_zero(profile.get("max_business_days")),
        "minMinutes": int_or_zero(profile.get("min_minutes")),
        "maxMinutes": int_or_zero(profile.get("max_minutes")),
        "display": str(profile.get("display_text") or ""),
        "schedulePriorityRank": int_or_zero(profile.get("schedule_priority_rank") or 90),
        "blockerType": str(profile.get("schedule_blocker_type") or "unknown"),
        "confidence": str(profile.get("confidence") or ""),
        "variance": str(profile.get("variance") or ""),
        "sourceAuthority": str(profile.get("source_authority") or ""),
        "sourceUrl": str(profile.get("source_url") or ""),
        "lastChecked": str(profile.get("last_checked") or ""),
        "notes": str(profile.get("notes") or ""),
    }


def int_or_zero(value: Any) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


def format_department(row: dict[str, Any], district: str) -> str:
    department = str(row.get("actual_department_name") or "").strip()
    team = str(row.get("actual_team_name") or "").strip()
    phone = str(row.get("phone") or "").strip()

    if district and department and district not in department and not is_regional_or_national_department(department):
        department = f"{district} {department}"

    label = " ".join(part for part in [department, team] if part)
    if phone:
        label = f"{label} ({phone})" if label else phone
    return label


def department_map_url(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    office_name = str(row.get("office_name") or "").strip()
    office_address = str(row.get("office_address") or "").strip()
    department = str(row.get("actual_department_name") or "").strip()
    if not office_address and not office_name:
        return ""
    query = " ".join(item for item in [office_address, office_name, department] if item)
    return f"https://map.naver.com/p/search/{quote(query)}"


def is_regional_or_national_department(name: str) -> bool:
    return any(token in name for token in ["관할", "홈택스", "국세", "세무서", "소방서", "서울소방"])


def should_use_department_issuer(title: str, current_issuer: str) -> bool:
    normalized_title = normalize(title)
    if "영업신고증" in normalized_title:
        return True
    if "사업자등록" in normalized_title:
        return True
    return "자치구" in current_issuer


def first_task_key(value: str) -> str:
    for token in re.split(r"[;,]\s*", value or ""):
        token = token.strip()
        if token:
            return token
    return ""


def split_summary(value: str) -> list[str]:
    items = [item.strip(" .") for item in re.split(r"[;·]\s*", value or "") if item.strip(" .")]
    return items[:4]


def unique_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for link in links:
        url = str(link.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({"label": str(link.get("label") or "안내 페이지"), "url": url})
    return result


def normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()
