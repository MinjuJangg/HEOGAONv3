from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from gms_client import gms_chat_json


HEOGAON_ROOT = Path(__file__).resolve().parents[1]
DEPARTMENT_DB = HEOGAON_ROOT / "department_mapping" / "seoul_department_mapping.sqlite"
DOCUMENT_DB = HEOGAON_ROOT / "document_issue_guide" / "document_issue_guide.sqlite"

SCHEMA_VERSION = "heogaon.inquiry_package.v1"


ACTION_TASK_KEYS: dict[str, list[str]] = {
    "open_food_business": ["food_business_report"],
    "check_building_use": ["building_register_issue", "building_use_review", "building_violation_review"],
    "check_same_place_history": ["food_admin_disposition_history"],
    "install_signboard": ["outdoor_ad_report"],
    "use_outdoor_space": ["road_occupation_permit"],
    "document_readiness": ["food_business_report", "business_registration"],
    "change_food_business": ["food_business_report", "building_use_review"],
}


DOCUMENT_TASK_KEYS: dict[str, list[str]] = {
    "fire_safety_certificate": ["fire_safety_completion"],
    "business_registration": ["business_registration"],
    "building_ledger_result": ["building_register_issue", "building_use_review"],
    "same_place_history_result": ["food_admin_disposition_history"],
    "signboard_application": ["outdoor_ad_report"],
    "signboard_owner_consent": ["outdoor_ad_report"],
    "signboard_photo_design": ["outdoor_ad_report"],
    "outdoor_space_materials": ["road_occupation_permit"],
    "outdoor_owner_consent": ["road_occupation_permit"],
}


DOCUMENT_SEARCH_TERMS: dict[str, str] = {
    "food_business_report": "식품 영업 신고서",
    "hygiene_training": "위생교육 수료증",
    "health_certificate": "건강진단결과서",
    "lease_contract": "임대차계약서 또는 시설사용계약서",
    "id_card": "신분증",
    "fire_safety_certificate": "안전시설등 완비증명서",
    "business_registration": "사업자등록증",
    "signboard_application": "옥외광고물",
    "signboard_owner_consent": "사용 승낙서",
    "signboard_photo_design": "간판",
    "outdoor_space_materials": "도로점용",
    "outdoor_owner_consent": "사용 승낙서",
    "building_ledger_result": "건축물대장",
    "same_place_history_result": "행정처분",
}


DOCUMENT_ACTION_LINKS: dict[str, dict[str, str]] = {
    "food_business_report": {
        "sourceTitle": "정부24 식품관련영업신고",
        "sourceUrl": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=14600000021&HighCtgCD=A09006&tp_seq=02",
    },
    "hygiene_training": {
        "sourceTitle": "한국외식업중앙회 위생교육",
        "sourceUrl": "https://www.ifoodedu.or.kr/",
    },
    "health_certificate": {
        "sourceTitle": "정부24 건강진단결과서(보건증) 발급",
        "sourceUrl": "https://www.gov.kr/portal/service/serviceInfo/135200000129",
    },
    "business_registration": {
        "sourceTitle": "국세청 홈택스",
        "sourceUrl": "https://www.hometax.go.kr",
    },
    "building_ledger_result": {
        "sourceTitle": "정부24 건축물대장 발급",
        "sourceUrl": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000098",
    },
    "signboard_application": {
        "sourceTitle": "정부24 옥외광고물 표시허가(신고)",
        "sourceUrl": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&HighCtgCD=A09006",
    },
    "outdoor_space_materials": {
        "sourceTitle": "정부24 도로점용허가",
        "sourceUrl": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000209&HighCtgCD=A09006",
    },
}


USER_PREPARED_DOCUMENT_IDS = {
    "lease_contract",
    "id_card",
    "signboard_owner_consent",
    "signboard_photo_design",
    "outdoor_owner_consent",
}


TASK_LABELS: dict[str, str] = {
    "food_business_report": "식품관련영업신고 및 영업신고증",
    "food_admin_disposition_history": "기존 업소 행정처분 이력 확인",
    "building_register_issue": "건축물대장 발급 및 열람",
    "building_use_review": "건축물 용도 적합성 확인",
    "building_violation_review": "위반건축물 여부 확인",
    "fire_safety_completion": "안전시설등 완비증명서",
    "outdoor_ad_report": "옥외광고물 표시허가 및 신고",
    "road_occupation_permit": "도로점용허가",
    "business_registration": "사업자등록 신청",
}


SCRIPT_SYSTEM_PROMPT = """
너는 허가온의 민원 문의 스크립트 작성 AI다.
제공된 사용자 상황, 담당 부서, 체크 항목, 서류 목록만 근거로
전화/온라인 문의에 바로 쓸 수 있는 짧은 한국어 문장을 만든다.

원칙:
1. 모르는 정보는 확정하지 말고 "확인 부탁드립니다"로 쓴다.
2. 사용자가 이미 준 주소, 층/호, 면적, 간판/외부공간 정보를 반영한다.
3. 담당 부서별로 물어볼 항목을 분리한다.
4. JSON 하나만 반환한다.
""".strip()


class InquiryScriptProviderUnavailable(RuntimeError):
    pass


def unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def tel_href(phone: str) -> str:
    digits = re.sub(r"[^0-9]", "", phone or "")
    return f"tel:{digits}" if digits else ""


def extract_district(slots: dict[str, Any]) -> str:
    for value in [
        slots.get("address", {}).get("full"),
        slots.get("address", {}).get("lookupAddress"),
        slots.get("address", {}).get("raw"),
    ]:
        match = re.search(r"([가-힣]+구)", str(value or ""))
        if match:
            return match.group(1)
    return ""


def all_document_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    plan = result.get("requirementGraph", {}).get("documentPlan", {})
    items = []
    for status_key in ["requiredForSubmission", "conditional", "later", "notRequiredByCurrentInputs"]:
        for item in plan.get(status_key, []):
            items.append({**item, "planBucket": status_key})
    return items


def derive_task_keys(result: dict[str, Any]) -> list[str]:
    graph = result.get("requirementGraph", {})
    keys: list[str] = []
    for action in graph.get("activatedActions", []):
        if action.get("status") in {"active", "reference", "conditional_if_planned"}:
            keys.extend(ACTION_TASK_KEYS.get(action.get("id") or "", []))
    for doc in all_document_items(result):
        if doc.get("status") in {"required", "needs_input", "conditional_if_planned", "later", "reference"}:
            keys.extend(DOCUMENT_TASK_KEYS.get(doc.get("id") or "", []))
    return unique(keys)


def fetch_department_rows(district: str, task_keys: list[str]) -> list[dict[str, Any]]:
    if not district or not DEPARTMENT_DB.exists():
        return []
    conn = sqlite3.connect(DEPARTMENT_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = []
        for task_key in task_keys:
            row = conn.execute(
                """
                SELECT *
                FROM department_mapping
                WHERE district_name = ? AND local_task_key = ?
                """,
                (district, task_key),
            ).fetchone()
            if row:
                rows.append(dict(row))
    finally:
        conn.close()
    return rows


def fallback_contact(task_key: str, district: str) -> dict[str, Any]:
    label = TASK_LABELS.get(task_key, task_key)
    return {
        "taskKey": task_key,
        "label": label,
        "departmentName": f"{district or '관할 구청'} {label} 담당",
        "teamName": "",
        "phone": "",
        "phoneHref": "",
        "sourceUrl": "",
        "sourceTitle": "fallback",
        "jurisdictionLevel": "district",
        "verifiedDate": "",
        "found": False,
    }


def normalize_contact(row: dict[str, Any], task_key: str) -> dict[str, Any]:
    return {
        "taskKey": task_key,
        "label": row.get("local_task_label") or TASK_LABELS.get(task_key, task_key),
        "departmentName": row.get("actual_department_name") or "",
        "teamName": row.get("actual_team_name") or "",
        "phone": row.get("phone") or "",
        "phoneHref": tel_href(row.get("phone") or ""),
        "sourceUrl": row.get("source_url") or "",
        "sourceTitle": row.get("source_title") or "",
        "jurisdictionLevel": row.get("jurisdiction_level") or "",
        "verifiedDate": row.get("last_verified_date") or "",
        "found": True,
    }


def build_contacts(district: str, task_keys: list[str]) -> list[dict[str, Any]]:
    rows_by_task = {row.get("local_task_key"): row for row in fetch_department_rows(district, task_keys)}
    return [
        normalize_contact(rows_by_task[task_key], task_key) if task_key in rows_by_task else fallback_contact(task_key, district)
        for task_key in task_keys
    ]


def fetch_document_guide(term: str, district: str) -> dict[str, Any] | None:
    if not term or not DOCUMENT_DB.exists():
        return None
    conn = sqlite3.connect(DOCUMENT_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT *
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
    if not row:
        return None
    item = dict(row)
    item["district"] = district
    return item


def build_document_guides(result: dict[str, Any], district: str) -> list[dict[str, Any]]:
    guides = []
    for doc in all_document_items(result):
        term = DOCUMENT_SEARCH_TERMS.get(doc.get("id") or "", doc.get("label") or "")
        guide = fetch_document_guide(term, district)
        action_link = document_action_link(doc.get("id") or "", guide)
        guides.append(
            {
                "documentId": doc.get("id"),
                "label": doc.get("label"),
                "status": doc.get("status"),
                "stage": doc.get("stage"),
                "condition": doc.get("condition", ""),
                "missingInputs": doc.get("missingInputs", []),
                "issueOrPreparePlace": (guide or {}).get("issue_or_prepare_place", ""),
                "issueChannel": (guide or {}).get("issue_channel", ""),
                "submitTo": (guide or {}).get("submit_to", ""),
                "whenNeeded": (guide or {}).get("when_needed", ""),
                "prerequisiteSummary": (guide or {}).get("prerequisite_summary", ""),
                "sourceUrl": action_link.get("sourceUrl", ""),
                "sourceTitle": action_link.get("sourceTitle", ""),
                "evidenceSourceUrl": (guide or {}).get("source_url", ""),
                "evidenceSourceTitle": (guide or {}).get("source_title", ""),
            }
        )
    return guides


def document_action_link(document_id: str, guide: dict[str, Any] | None) -> dict[str, str]:
    if document_id in USER_PREPARED_DOCUMENT_IDS:
        return {"sourceUrl": "", "sourceTitle": ""}
    explicit = DOCUMENT_ACTION_LINKS.get(document_id)
    if explicit:
        return explicit
    url = str((guide or {}).get("source_url") or "")
    if "gov.kr" in url or "hometax.go.kr" in url:
        return {
            "sourceUrl": url,
            "sourceTitle": str((guide or {}).get("source_title") or "공식 신청/발급 안내"),
        }
    return {"sourceUrl": "", "sourceTitle": ""}


def build_check_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for missing in result.get("requirementGraph", {}).get("missingInputs", []):
        items.append(
            {
                "id": f"missing_{missing.get('id')}",
                "type": "missing_input",
                "status": "needs_user_input",
                "label": missing.get("id"),
                "reason": missing.get("reason"),
                "requiredBy": missing.get("requiredBy", []),
            }
        )
    api = result.get("apiPlan", {})
    external = result.get("externalChecks") or {}
    if api.get("canRunBuildingLedgerApi"):
        items.append(
            {
                "id": "building_ledger_api",
                "type": "api_check",
                "status": (external.get("buildingLedger") or {}).get("status", "not_run"),
                "label": "건축물대장 조회",
                "reason": "건축물 용도, 층별 용도, 위반건축물 여부 확인",
            }
        )
    if api.get("canRunPastBusinessLookup"):
        items.append(
            {
                "id": "past_business_lookup",
                "type": "api_check",
                "status": (external.get("pastBusinessLookup") or {}).get("status", "not_run"),
                "label": "동일 장소 인허가/행정처분 이력 조회",
                "reason": "기존 업소 이력과 행정처분 영향 확인",
            }
        )
    return items


def build_situation_summary(result: dict[str, Any]) -> str:
    slots = result.get("slots", {})
    address = slots.get("address", {})
    business = slots.get("business", {})
    space = slots.get("space", {})
    facility = slots.get("facility", {})
    recommended_types, review_types = business_type_groups(business)
    parts = [
        f"민원 목적: {slots.get('intent')}",
        f"주소: {address.get('full') or address.get('raw') or '미입력'}",
        f"추천 업종: {', '.join(recommended_types) or business.get('concept') or '미정'}",
    ]
    if review_types:
        parts.append(f"검토 후보: {', '.join(review_types)}")
    if space.get("areaM2"):
        parts.append(f"면적: {space.get('areaM2')}㎡")
    if business.get("liquorSales") is not None:
        parts.append(f"주류 판매: {'예' if business.get('liquorSales') else '아니오'}")
    if facility.get("signboard"):
        parts.append(f"간판: {facility.get('signboardType') or '설치 예정'} {facility.get('signboardSizeText') or ''}".strip())
    if facility.get("outdoorSpace"):
        parts.append(f"외부공간: {facility.get('outdoorLocation') or '사용 예정'} {facility.get('outdoorTableCount') or ''}".strip())
    return " / ".join(parts)


def business_type_groups(business: dict[str, Any]) -> tuple[list[str], list[str]]:
    recommended: list[str] = []
    review: list[str] = []
    for route in business.get("candidateRoutes") or []:
        business_type = route.get("businessType")
        if not business_type:
            continue
        if route.get("status") == "candidate":
            recommended.append(business_type)
        else:
            review.append(business_type)
    if not recommended:
        for item in business.get("candidateTypes") or []:
            if item not in recommended:
                recommended.append(item)
    return unique(recommended), unique(review)


def questions_for_task(task_key: str, result: dict[str, Any]) -> list[str]:
    base = {
        "food_business_report": [
            "현재 조건에서 어떤 식품접객업 신고 유형으로 보는 것이 맞는지 확인 부탁드립니다.",
            "영업신고 전 반드시 준비해야 하는 서류와 제출 순서를 확인 부탁드립니다.",
        ],
        "food_admin_disposition_history": [
            "같은 장소에 기존 업소 또는 동일 업종 행정처분 이력이 있는지 확인 부탁드립니다.",
            "기존 업소 이력이 새 영업신고나 인수 절차에 영향을 주는지 확인 부탁드립니다.",
        ],
        "building_register_issue": [
            "해당 주소의 건축물대장 열람 결과에서 주용도, 층별 용도, 위반건축물 여부를 확인하려고 합니다.",
        ],
        "building_use_review": [
            "해당 층/호수가 희망 업종 영업에 적합한 건축물 용도인지 확인 부탁드립니다.",
            "용도변경이나 추가 확인이 필요한지 확인 부탁드립니다.",
        ],
        "building_violation_review": [
            "해당 건물이 위반건축물로 표시되어 있는지, 영업신고에 영향이 있는지 확인 부탁드립니다.",
        ],
        "fire_safety_completion": [
            "층과 면적 기준상 안전시설등 완비증명서가 필요한지 확인 부탁드립니다.",
        ],
        "outdoor_ad_report": [
            "설치하려는 간판이 옥외광고물 표시허가 또는 신고 대상인지 확인 부탁드립니다.",
            "간판 크기, 설치 위치, 제출 도안/사진 기준을 확인 부탁드립니다.",
        ],
        "road_occupation_permit": [
            "외부 테이블 위치가 도로점용허가 대상인지 확인 부탁드립니다.",
            "필요한 위치도, 현장 사진, 사용 면적 도면 기준을 확인 부탁드립니다.",
        ],
        "business_registration": [
            "영업신고증 발급 이후 사업자등록 진행 시 필요한 항목을 확인 부탁드립니다.",
        ],
    }
    questions = list(base.get(task_key, ["현재 조건에서 필요한 인허가 절차와 준비 서류를 확인 부탁드립니다."]))
    for question in (result.get("aiJudgement") or {}).get("judgement", {}).get("questionsToAsk", []):
        if question.get("question"):
            questions.append(question["question"])
    return unique(questions)


def rule_script_for_contact(contact: dict[str, Any], result: dict[str, Any]) -> dict[str, str]:
    summary = build_situation_summary(result)
    questions = questions_for_task(contact["taskKey"], result)
    subject = f"{contact['label']} 문의"
    body = "[상황 요약]\n" + summary + "\n\n[문의할 내용]\n"
    body += "\n".join(f"{idx + 1}. {question}" for idx, question in enumerate(questions))
    body += "\n\n[확인 받고 싶은 답변]\n- 필요 서류\n- 제출/신고 순서\n- 담당 부서가 다를 경우 정확한 이관 부서\n- 추가로 준비해야 할 자료"
    return {
        "subject": subject,
        "body": body,
        "phoneScript": f"안녕하세요. {summary} 건으로 {contact['label']} 관련 확인을 부탁드리려고 전화드렸습니다. " + " ".join(questions[:2]),
    }


def build_rule_scripts(contacts: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    scripts = []
    for contact in contacts:
        scripts.append({"taskKey": contact["taskKey"], "departmentName": contact["departmentName"], **rule_script_for_contact(contact, result)})
    if scripts:
        online = scripts[0]
    else:
        online = {"subject": "인허가 문의", "body": build_situation_summary(result), "phoneScript": ""}
    return {
        "provider": "rule",
        "scripts": scripts,
        "onlineDraft": {"subject": online["subject"], "body": online["body"]},
    }


def compact_contact_for_prompt(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "taskKey": contact.get("taskKey"),
        "label": contact.get("label"),
        "departmentName": contact.get("departmentName"),
        "teamName": contact.get("teamName"),
        "phone": contact.get("phone"),
        "found": contact.get("found"),
    }


def compact_check_item_for_prompt(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "status": item.get("status"),
        "label": item.get("label"),
        "reason": item.get("reason"),
    }


def compact_document_for_prompt(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "label": item.get("label"),
        "status": item.get("status"),
        "stage": item.get("stage"),
        "condition": item.get("condition", ""),
        "missingInputs": (item.get("missingInputs") or [])[:5],
    }


def document_labels(items: Any, limit: int = 12) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get("label") or item.get("id")) for item in items[:limit] if isinstance(item, dict) and (item.get("label") or item.get("id"))]


def compact_script_context(result: dict[str, Any]) -> dict[str, Any]:
    graph = result.get("requirementGraph", {})
    document_plan = graph.get("documentPlan", {})
    judgement = (result.get("aiJudgement") or {}).get("judgement", {})
    slots = result.get("slots", {})
    business = slots.get("business") or {}
    recommended_types, review_types = business_type_groups(business)
    return {
        "inputText": result.get("inputText"),
        "intent": slots.get("intent"),
        "address": slots.get("address"),
        "business": {
            "concept": business.get("concept"),
            "requestedType": business.get("requestedType"),
            "recommendedTypes": recommended_types,
            "reviewOnlyTypes": review_types,
            "liquorSales": business.get("liquorSales"),
            "salesItems": business.get("salesItems"),
            "takeoverOrExistingBusiness": business.get("takeoverOrExistingBusiness"),
        },
        "space": slots.get("space"),
        "facility": slots.get("facility"),
        "procedurePlan": [
            {
                "order": item.get("order"),
                "title": item.get("title"),
                "status": item.get("status"),
            }
            for item in graph.get("procedurePlan", [])[:10]
        ],
        "documentPlan": {
            "required": document_labels(document_plan.get("requiredForSubmission"), 12),
            "conditional": document_labels(document_plan.get("conditional"), 12),
            "later": document_labels(document_plan.get("later"), 8),
        },
        "aiJudgement": {
            "decisionStatus": judgement.get("decisionStatus"),
            "summary": judgement.get("summary"),
            "questionsToAsk": (judgement.get("questionsToAsk") or [])[:8],
            "documentSummary": judgement.get("documentSummary"),
            "departmentSummary": judgement.get("departmentSummary"),
        },
    }


def build_llm_script_prompt(result: dict[str, Any], contacts: list[dict[str, Any]], check_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "system": SCRIPT_SYSTEM_PROMPT,
        "user": {
            "schemaVersion": SCHEMA_VERSION,
            "situationSummary": build_situation_summary(result),
            "contacts": [compact_contact_for_prompt(contact) for contact in contacts[:10]],
            "checkItems": [compact_check_item_for_prompt(item) for item in check_items[:16]],
            "context": compact_script_context(result),
            "requiredShape": {
                "scripts": [{"taskKey": "string", "subject": "string", "body": "string", "phoneScript": "string"}],
                "onlineDraft": {"subject": "string", "body": "string"},
            },
            "writingRules": [
                "recommendedTypes는 현재 추천 경로로 쓰고, reviewOnlyTypes는 필요 시 '검토 후보'라고만 표현한다.",
                "reviewOnlyTypes를 사용자가 선택 예정이라고 단정하지 않는다.",
                "각 scripts 항목은 contacts의 taskKey에 맞춰 작성한다.",
            ],
        },
    }


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    return json.loads(stripped)


def openai_scripts(result: dict[str, Any], contacts: list[dict[str, Any]], check_items: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise InquiryScriptProviderUnavailable("OPENAI_API_KEY is not set.")
    model = os.getenv("HEOGAON_AI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = build_llm_script_prompt(result, contacts, check_items)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": json.dumps(prompt["user"], ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {message}") from exc
    content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    parsed = parse_json_object(content)
    parsed["provider"] = "openai"
    return parsed


def gms_scripts(result: dict[str, Any], contacts: list[dict[str, Any]], check_items: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = build_llm_script_prompt(result, contacts, check_items)
    parsed = gms_chat_json(
        system_prompt=prompt["system"],
        user_payload=prompt["user"],
        temperature=0.2,
        max_output_tokens=3600,
        timeout=60,
    )
    parsed.pop("_gmsMeta", None)
    parsed["provider"] = "gms"
    return parsed


def generate_scripts(result: dict[str, Any], contacts: list[dict[str, Any]], check_items: list[dict[str, Any]], provider: str, fallback_to_rule: bool) -> dict[str, Any]:
    provider = (provider or "rule").lower()
    meta = {"requestedProvider": provider, "provider": provider, "fallbackUsed": False, "fallbackReason": ""}
    try:
        if provider == "rule":
            scripts = build_rule_scripts(contacts, result)
        elif provider == "openai":
            scripts = openai_scripts(result, contacts, check_items)
        elif provider == "gms":
            scripts = gms_scripts(result, contacts, check_items)
        else:
            raise ValueError(f"Unknown inquiry provider: {provider}")
    except Exception as exc:
        if not fallback_to_rule:
            raise
        meta.update({"provider": "rule", "fallbackUsed": True, "fallbackReason": f"{type(exc).__name__}: {exc}"})
        scripts = build_rule_scripts(contacts, result)
    attach_contact_db_mapping(scripts, contacts, result)
    scripts["meta"] = meta
    return scripts


def contact_payload(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "taskKey": contact.get("taskKey"),
        "label": contact.get("label"),
        "departmentName": contact.get("departmentName"),
        "teamName": contact.get("teamName"),
        "phone": contact.get("phone"),
        "phoneHref": contact.get("phoneHref"),
        "sourceUrl": contact.get("sourceUrl"),
        "sourceTitle": contact.get("sourceTitle"),
        "jurisdictionLevel": contact.get("jurisdictionLevel"),
        "verifiedDate": contact.get("verifiedDate"),
        "found": contact.get("found"),
    }


def attach_contact_to_script(script: dict[str, Any], contact: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    fallback = rule_script_for_contact(contact, result)
    mapped = {
        **script,
        "taskKey": contact.get("taskKey"),
        "label": contact.get("label"),
        "departmentName": contact.get("departmentName"),
        "teamName": contact.get("teamName"),
        "phone": contact.get("phone"),
        "phoneHref": contact.get("phoneHref"),
        "contactFound": contact.get("found"),
        "contactSourceUrl": contact.get("sourceUrl"),
        "contact": contact_payload(contact),
        "contactMapped": True,
    }
    mapped["subject"] = mapped.get("subject") or fallback["subject"]
    mapped["body"] = mapped.get("body") or fallback["body"]
    mapped["phoneScript"] = mapped.get("phoneScript") or fallback["phoneScript"]
    return mapped


def attach_contact_db_mapping(scripts: dict[str, Any], contacts: list[dict[str, Any]], result: dict[str, Any]) -> None:
    """Make contact DB the source of truth for every inquiry script."""
    contacts_by_task = {contact.get("taskKey"): contact for contact in contacts}
    scripts_by_task: dict[str, dict[str, Any]] = {}
    for script in scripts.get("scripts") or []:
        if not isinstance(script, dict) or script.get("taskKey") not in contacts_by_task:
            continue
        scripts_by_task.setdefault(script.get("taskKey"), script)

    ordered_scripts = []
    for contact in contacts:
        task_key = contact.get("taskKey")
        script = scripts_by_task.get(task_key) or {"taskKey": task_key}
        ordered_scripts.append(attach_contact_to_script(script, contact, result))
    scripts["scripts"] = ordered_scripts
    scripts["contactMapping"] = [contact_payload(contact) for contact in contacts]

    if ordered_scripts:
        online = scripts.get("onlineDraft") or {}
        online.setdefault("subject", ordered_scripts[0].get("subject") or "인허가 문의")
        online.setdefault("body", ordered_scripts[0].get("body") or build_situation_summary(result))
        online["primaryContact"] = ordered_scripts[0].get("contact")
        scripts["onlineDraft"] = online


def channel_package(contacts: list[dict[str, Any]], district: str) -> list[dict[str, str]]:
    first_phone = next((contact for contact in contacts if contact.get("phoneHref")), None)
    first_url = next((contact for contact in contacts if contact.get("sourceUrl")), None)
    channels = []
    if first_phone:
        channels.append(
            {
                "id": "phone",
                "name": f"{first_phone['departmentName']} 전화",
                "icon": "phone",
                "recommended": True,
                "primaryAction": "call",
                "primaryUrl": first_phone["phoneHref"],
            }
        )
    channels.append(
        {
            "id": "online",
            "name": "국민신문고 또는 구청 온라인 문의",
            "icon": "monitor",
            "recommended": not bool(first_phone),
            "primaryAction": "open",
            "primaryUrl": "https://www.epeople.go.kr/index.jsp",
        }
    )
    if first_url:
        channels.append(
            {
                "id": "department_page",
                "name": f"{district or '관할'} 부서 안내 페이지",
                "icon": "building",
                "recommended": False,
                "primaryAction": "open",
                "primaryUrl": first_url["sourceUrl"],
            }
        )
    return channels


def build_inquiry_package(
    result: dict[str, Any],
    provider: str = "rule",
    fallback_to_rule: bool = True,
) -> dict[str, Any]:
    slots = result.get("slots", {})
    district = extract_district(slots)
    task_keys = derive_task_keys(result)
    contacts = build_contacts(district, task_keys)
    documents = build_document_guides(result, district)
    check_items = build_check_items(result)
    scripts = generate_scripts(result, contacts, check_items, provider=provider, fallback_to_rule=fallback_to_rule)
    active = contacts[0] if contacts else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "ok",
        "district": district,
        "taskKeys": task_keys,
        "activeInquiry": active,
        "contacts": contacts,
        "channels": channel_package(contacts, district),
        "documentGuides": documents,
        "checkItems": check_items,
        "scripts": scripts,
        "frontendHints": {
            "primarySections": ["contacts", "scripts", "documentGuides", "checkItems"],
            "copyableFields": ["scripts.onlineDraft.subject", "scripts.onlineDraft.body", "contacts.phone"],
        },
    }
