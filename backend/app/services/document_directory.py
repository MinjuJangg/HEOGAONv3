from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from app.services.slot_utils import slot_value


REPO_ROOT = Path(__file__).resolve().parents[3]
DOCUMENT_DB = REPO_ROOT / "minju" / "document_issue_guide" / "document_issue_guide.sqlite"
DEPARTMENT_DB = REPO_ROOT / "minju" / "department_mapping" / "seoul_department_mapping.sqlite"


TITLE_RULES: list[tuple[list[str], str, str]] = [
    (["지위승계", "승계 신고", "양도", "양수"], "영업자 지위승계", "food_business_report"),
    (["임대차", "사용권한", "사용 권한"], "임대차", "food_business_report"),
    (["신분증"], "신분증", "food_business_report"),
    (["위생교육"], "위생교육", "food_business_report"),
    (["건강진단", "보건증"], "건강진단", "food_business_report"),
    (["소방완비", "안전시설"], "안전시설", "food_business_report"),
    (["영업 신고서", "영업신고서"], "식품 영업 신고서", "food_business_report"),
    (["영업신고증"], "식품접객업 영업신고증", "business_registration"),
    (["사업자등록"], "사업자등록", "business_registration"),
    (["옥외광고", "간판", "원색도안"], "옥외광고물", "outdoor_ad_report"),
    (["도로점용", "외부공간", "외부 공간", "테이블"], "도로점용", "road_occupation_permit"),
]


ISSUER_TASK_RULES: list[tuple[list[str], str]] = [
    (["지위승계", "승계 신고"], "food_business_report"),
    (["영업신고증"], "food_business_report"),
    (["소방완비", "안전시설"], "fire_safety_completion"),
    (["사업자등록"], "business_registration"),
    (["옥외광고", "간판", "원색도안"], "outdoor_ad_report"),
    (["도로점용", "외부공간", "외부 공간", "테이블"], "road_occupation_permit"),
]


def lookup_document_directory(case: dict[str, Any], title: str) -> dict[str, Any]:
    district = extract_district(case)
    term, submit_task_key = term_and_submit_task(title)
    guide = fetch_document_guide(term) if term else None

    guide_task_key = first_task_key((guide or {}).get("submit_to_local_task_key") or "")
    submit_task_key = submit_task_key or guide_task_key
    issuer_task_key = issuer_task_for(title)

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

    issuer_url = ""
    issuer_label = ""
    if issuer_department and (issuer_department.get("source_url") or ""):
        issuer_url = str(issuer_department.get("source_url") or "")
        issuer_label = str(issuer_department.get("source_title") or "발급처 안내")
    elif guide and guide.get("source_url"):
        issuer_url = str(guide.get("source_url") or "")
        issuer_label = str(guide.get("source_title") or "발급/준비 안내")

    submit_url = str((submit_department or {}).get("source_url") or "")
    submit_label = str((submit_department or {}).get("source_title") or "제출처 안내")

    official_links = unique_links(
        [
            {
                "label": issuer_label or str((guide or {}).get("source_title") or "발급/준비 안내"),
                "url": issuer_url or str((guide or {}).get("source_url") or ""),
            },
            {"label": submit_label, "url": submit_url},
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
    }


def extract_district(case: dict[str, Any]) -> str:
    summary = ((case.get("minjuIntake") or {}).get("summary") or {}) or ((case.get("minjuDraft") or {}).get("summary") or {})
    summary_slots = summary.get("slots") or {}
    address = summary_slots.get("address") or {}
    candidates = [
        case.get("rawInput"),
        slot_value(case, "exact_address"),
        slot_value(case, "location"),
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
            ORDER BY graph_requirement_count DESC, document_name
            LIMIT 1
            """,
            (f"%{term}%",),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


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
                   source_title
            FROM department_mapping
            WHERE district_name = ? AND local_task_key = ?
            LIMIT 1
            """,
            (district, task_key),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


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
