from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any


INTAKE_DIR = Path(__file__).resolve().parent
MINJU_ROOT = INTAKE_DIR.parent
DOCUMENT_DB_PATH = MINJU_ROOT / "document_issue_guide" / "document_issue_guide.sqlite"


DOC_PROCESSING_PROFILE: dict[str, str] = {
    "building_ledger_result": "building_register",
    "same_place_history_result": "same_place_history_lookup",
    "food_business_report": "food_business_report",
    "hygiene_training": "hygiene_training",
    "health_certificate": "health_certificate",
    "lease_contract": "applicant_prepared_document",
    "id_card": "applicant_prepared_document",
    "fire_safety_certificate": "fire_safety_completion",
    "lpg_completion_certificate": "lpg_completion",
    "business_registration": "business_registration",
    "signboard_application": "outdoor_ad_report",
    "signboard_owner_consent": "applicant_prepared_document",
    "signboard_photo_design": "applicant_prepared_document",
    "outdoor_space_materials": "road_occupation_permit",
    "outdoor_owner_consent": "applicant_prepared_document",
}


BLOCKER_WEIGHTS = {
    "critical_prerequisite": 45,
    "conditional_long_lead": 40,
    "unblocks_validation": 35,
    "parallel_optional_permit": 25,
    "user_input_or_attachment": 20,
    "submission_after_prerequisites": 12,
    "after_food_report": 8,
    "after_business_registration": 6,
    "unknown": 0,
}

STATUS_WEIGHTS = {
    "required": 35,
    "needs_input": 30,
    "conditional_if_planned": 20,
    "reference": 10,
    "later": 5,
    "not_required_by_current_inputs": -20,
}

DEFAULT_PROFILE = {
    "profile_id": "not_found",
    "processing_time_scope": "not_found",
    "processing_time_kind": "no_public_processing_time_found",
    "min_business_days": "",
    "max_business_days": "",
    "min_minutes": "",
    "max_minutes": "",
    "display_text": "official processing time unknown",
    "schedule_priority_rank": "90",
    "schedule_blocker_type": "unknown",
    "confidence": "low",
    "variance": "unknown",
    "source_authority": "",
    "source_url": "",
    "last_checked": "2026-06-13",
    "notes": "No official public processing time was matched for this document.",
}

SEQUENCE_RANK_BY_BLOCKER = {
    "unblocks_validation": 10,
    "critical_prerequisite": 20,
    "conditional_long_lead": 20,
    "user_input_or_attachment": 30,
    "parallel_optional_permit": 40,
    "submission_after_prerequisites": 60,
    "after_food_report": 70,
    "after_business_registration": 80,
    "unknown": 90,
}

DOC_SEQUENCE_RANK = {
    "building_ledger_result": 10,
    "same_place_history_result": 12,
    "health_certificate": 20,
    "hygiene_training": 20,
    "fire_safety_certificate": 20,
    "lpg_completion_certificate": 20,
    "lease_contract": 30,
    "id_card": 30,
    "signboard_owner_consent": 30,
    "signboard_photo_design": 30,
    "outdoor_owner_consent": 30,
    "signboard_application": 40,
    "outdoor_space_materials": 40,
    "food_business_report": 60,
    "business_registration": 70,
}


def int_or_zero(value: Any) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


@lru_cache(maxsize=1)
def load_processing_profiles() -> dict[str, dict[str, str]]:
    if not DOCUMENT_DB_PATH.exists():
        return {"not_found": DEFAULT_PROFILE}
    conn = sqlite3.connect(DOCUMENT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute("SELECT * FROM service_processing_times").fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()
    profiles = {str(row["profile_id"]): dict(row) for row in rows}
    profiles.setdefault("not_found", DEFAULT_PROFILE)
    return profiles


def normalize_processing_time(profile: dict[str, str]) -> dict[str, Any]:
    return {
        "profileId": profile.get("profile_id", "not_found"),
        "scope": profile.get("processing_time_scope", ""),
        "kind": profile.get("processing_time_kind", ""),
        "minBusinessDays": int_or_zero(profile.get("min_business_days")),
        "maxBusinessDays": int_or_zero(profile.get("max_business_days")),
        "minMinutes": int_or_zero(profile.get("min_minutes")),
        "maxMinutes": int_or_zero(profile.get("max_minutes")),
        "display": profile.get("display_text", ""),
        "schedulePriorityRank": int_or_zero(profile.get("schedule_priority_rank") or 90),
        "blockerType": profile.get("schedule_blocker_type", "unknown"),
        "confidence": profile.get("confidence", ""),
        "variance": profile.get("variance", ""),
        "sourceAuthority": profile.get("source_authority", ""),
        "sourceUrl": profile.get("source_url", ""),
        "lastChecked": profile.get("last_checked", ""),
        "notes": profile.get("notes", ""),
    }


def profile_for_doc(doc_id: str) -> dict[str, Any]:
    profiles = load_processing_profiles()
    profile_id = DOC_PROCESSING_PROFILE.get(doc_id, "not_found")
    return normalize_processing_time(profiles.get(profile_id, profiles["not_found"]))


def enrich_document(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    enriched["processingTime"] = profile_for_doc(str(item.get("id") or ""))
    return enriched


def duration_weight(processing_time: dict[str, Any]) -> int:
    days = int_or_zero(processing_time.get("maxBusinessDays"))
    minutes = int_or_zero(processing_time.get("maxMinutes"))
    return min(25, days * 4 + round(minutes / 360))


def duration_sort_units(processing_time: dict[str, Any]) -> int:
    days = int_or_zero(processing_time.get("maxBusinessDays"))
    minutes = int_or_zero(processing_time.get("maxMinutes"))
    return days * 1440 + minutes


def priority_score(item: dict[str, Any]) -> int:
    processing_time = item.get("processingTime") or {}
    rank = int_or_zero(processing_time.get("schedulePriorityRank") or 90)
    blocker = str(processing_time.get("blockerType") or "unknown")
    status = str(item.get("status") or "")
    score = 100 - min(rank, 100)
    score += STATUS_WEIGHTS.get(status, 0)
    score += BLOCKER_WEIGHTS.get(blocker, 0)
    score += duration_weight(processing_time)
    if item.get("missingInputs"):
        score += 8
    return score


def sequence_rank(item: dict[str, Any]) -> int:
    status = str(item.get("status") or "")
    if status == "needs_input":
        return 5
    doc_id = str(item.get("id") or "")
    if doc_id in DOC_SEQUENCE_RANK:
        return DOC_SEQUENCE_RANK[doc_id]
    blocker = str((item.get("processingTime") or {}).get("blockerType") or "unknown")
    return SEQUENCE_RANK_BY_BLOCKER.get(blocker, 90)


def recommended_start(item: dict[str, Any]) -> str:
    blocker = str((item.get("processingTime") or {}).get("blockerType") or "unknown")
    doc_id = str(item.get("id") or "")
    if blocker == "critical_prerequisite":
        return "today"
    if blocker == "conditional_long_lead":
        return "as_soon_as_condition_confirmed"
    if blocker == "unblocks_validation":
        return "when_address_is_known"
    if blocker == "parallel_optional_permit":
        return "parallel_after_user_confirms_plan"
    if blocker == "user_input_or_attachment":
        return "collect_now"
    if doc_id == "food_business_report":
        return "after_prerequisite_documents_ready"
    if doc_id == "business_registration":
        return "after_food_business_report_certificate"
    return "when_relevant"


def calendar_lane(item: dict[str, Any]) -> str:
    blocker = str((item.get("processingTime") or {}).get("blockerType") or "unknown")
    if blocker in {"critical_prerequisite", "conditional_long_lead"}:
        return "long_lead_prerequisites"
    if blocker == "unblocks_validation":
        return "validation"
    if blocker == "parallel_optional_permit":
        return "parallel_optional_permits"
    if blocker == "user_input_or_attachment":
        return "user_prepared_documents"
    if blocker in {"submission_after_prerequisites", "after_food_report", "after_business_registration"}:
        return "submission_sequence"
    return "review_or_unknown"


def depends_on(item: dict[str, Any]) -> list[str]:
    doc_id = str(item.get("id") or "")
    if doc_id == "food_business_report":
        return ["hygiene_training", "health_certificate", "lease_contract", "id_card"]
    if doc_id == "business_registration":
        return ["food_business_report"]
    if doc_id in {"signboard_application", "signboard_owner_consent", "signboard_photo_design"}:
        return ["signboard_plan_confirmed"]
    if doc_id in {"outdoor_space_materials", "outdoor_owner_consent"}:
        return ["outdoor_space_plan_confirmed"]
    if doc_id == "fire_safety_certificate":
        return ["floor_area_condition_confirmed"]
    if doc_id == "lpg_completion_certificate":
        return ["lpg_use_confirmed"]
    return []


def schedule_task(item: dict[str, Any]) -> dict[str, Any]:
    processing_time = item.get("processingTime") or {}
    return {
        "documentId": item.get("id"),
        "label": item.get("label"),
        "status": item.get("status"),
        "stage": item.get("stage"),
        "priorityScore": priority_score(item),
        "durationSortUnits": duration_sort_units(processing_time),
        "sequenceRank": sequence_rank(item),
        "recommendedStart": recommended_start(item),
        "calendarLane": calendar_lane(item),
        "dependsOn": depends_on(item),
        "processingTime": processing_time,
        "condition": item.get("condition", ""),
        "missingInputs": item.get("missingInputs") or [],
    }


def unique_docs(document_plan: dict[str, Any]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for bucket in ["requiredForSubmission", "conditional", "later", "notRequiredByCurrentInputs"]:
        for item in document_plan.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("id") or item.get("label") or "")
            if doc_id and doc_id not in by_id:
                by_id[doc_id] = item
    return list(by_id.values())


def not_required_action_doc_ids(graph: dict[str, Any]) -> set[str]:
    action_status = {
        str(item.get("id") or ""): str(item.get("status") or "")
        for item in graph.get("activatedActions", [])
        if isinstance(item, dict)
    }
    doc_statuses: dict[str, set[str]] = {}
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict) or edge.get("type") != "requires_document":
            continue
        action_id = str(edge.get("from") or "")
        doc_id = str(edge.get("to") or "")
        status = action_status.get(action_id)
        if action_id and doc_id and status:
            doc_statuses.setdefault(doc_id, set()).add(status)
    return {
        doc_id
        for doc_id, statuses in doc_statuses.items()
        if statuses and statuses <= {"not_required_now"}
    }


def schedule_not_required_task(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized["status"] = "not_required_by_current_inputs"
    return schedule_task(normalized)


def build_schedule_plan(graph: dict[str, Any]) -> dict[str, Any]:
    document_plan = graph.get("documentPlan") or {}
    all_docs = unique_docs(document_plan)
    not_required_by_action = not_required_action_doc_ids(graph)
    active_docs = [
        item
        for item in all_docs
        if str(item.get("status") or "") != "not_required_by_current_inputs"
        and str(item.get("id") or "") not in not_required_by_action
    ]
    not_required_docs = [
        schedule_not_required_task(item)
        for item in all_docs
        if str(item.get("status") or "") == "not_required_by_current_inputs"
        or str(item.get("id") or "") in not_required_by_action
    ]
    tasks = [schedule_task(item) for item in active_docs]
    tasks.sort(
        key=lambda item: (
            int_or_zero(item.get("sequenceRank") or 90),
            -int_or_zero(item.get("durationSortUnits")),
            -int_or_zero(item.get("priorityScore")),
            str(item.get("label") or ""),
        )
    )
    by_lane: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        by_lane.setdefault(str(task.get("calendarLane") or "review_or_unknown"), []).append(task)

    return {
        "version": "heogaon.schedule_plan.v1",
        "basis": "official_processing_times_and_document_dependencies",
        "policy": [
            "Start validation and long-lead prerequisites before final submissions.",
            "Run optional permit tracks in parallel after the user confirms the plan.",
            "Keep food business report after prerequisite documents are ready.",
            "Keep business registration after the food business report certificate.",
            "Use source confidence and variance to decide when to confirm with the district office.",
        ],
        "priorityFormula": {
            "inputs": ["sequenceRank", "parallelDuration", "status", "blockerType", "officialDuration", "schedulePriorityRank", "missingInputs"],
            "higherScoreMeans": "tie_breaker_after_sequence_rank_and_parallel_duration",
        },
        "priorityQueue": tasks,
        "notRequired": not_required_docs,
        "parallelTracks": by_lane,
        "criticalPath": [
            "building_ledger_result",
            "same_place_history_result",
            "health_certificate",
            "hygiene_training",
            "fire_safety_certificate_if_required",
            "lpg_completion_certificate_if_required",
            "food_business_report",
            "business_registration",
        ],
        "calendarStrategy": {
            "withoutTargetDate": "Use relative milestones: validation first, long-lead prerequisites today, final submissions after prerequisites.",
            "withTargetOpeningDate": "Back-schedule from the opening date using maxBusinessDays and keep local-variance items buffered.",
            "bufferPolicy": "Add buffer for district_specific, permit_type_specific, local_variance, fire/LPG, and optional permit profiles.",
        },
    }


def enrich_requirement_graph_schedule(graph: dict[str, Any]) -> dict[str, Any]:
    document_plan = graph.get("documentPlan") or {}
    enriched_plan = {}
    for bucket, items in document_plan.items():
        if isinstance(items, list):
            enriched_plan[bucket] = [enrich_document(item) if isinstance(item, dict) else item for item in items]
        else:
            enriched_plan[bucket] = items
    enriched_graph = {**graph, "documentPlan": enriched_plan}
    enriched_graph["schedulePlan"] = build_schedule_plan(enriched_graph)
    return enriched_graph
