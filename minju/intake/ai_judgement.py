from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from gms_client import gms_chat_json


SCHEMA_VERSION = "heogaon.ai_judgement.v1"


AI_JUDGEMENT_SYSTEM_PROMPT = """
너는 허가온의 AI judgement agent다.
사용자 자연어, slot filling 결과, API/decision 결과, requirement graph를 한 번에 보고
최종 안내에 필요한 구조화 판단 JSON을 만든다.

중요 원칙:
1. 제공된 structured context에 없는 사실을 확정하지 않는다.
2. API/건축물대장/인허가 이력이 미조회면 "확정 불가"로 표시한다.
3. 그래프가 산출한 서류/부서/부족정보를 우선한다.
4. 사용자가 추가로 준 정보가 있으면 지금 당장 묻지 않는다.
5. 결과는 JSON 하나만 반환한다.
""".strip()


class AIJudgementProviderUnavailable(RuntimeError):
    pass


def compact_for_ai(result: dict[str, Any]) -> dict[str, Any]:
    def first_items(value: Any, limit: int) -> Any:
        if isinstance(value, list):
            return value[:limit]
        if isinstance(value, dict):
            return dict(list(value.items())[:limit])
        return value

    def pick(value: dict[str, Any], keys: list[str]) -> dict[str, Any]:
        return {key: value.get(key) for key in keys if key in value}

    def compact_route(route: dict[str, Any]) -> dict[str, Any]:
        return {
            "permitType": route.get("permitType") or route.get("businessType"),
            "status": route.get("status"),
            "label": route.get("label"),
            "score": route.get("score"),
            "reasons": (route.get("reasons") or [])[:3],
            "needsForFinal": (route.get("needsForFinal") or [])[:5],
        }

    def compact_question(item: dict[str, Any]) -> dict[str, Any]:
        return pick(item, ["id", "label", "question", "reason"])

    def compact_doc(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "label": item.get("label"),
            "status": item.get("status"),
            "stage": item.get("stage"),
            "condition": item.get("condition", ""),
            "missingInputs": (item.get("missingInputs") or [])[:5],
        }

    def compact_procedure(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "order": item.get("order"),
            "id": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "documents": (item.get("documents") or [])[:6],
            "departments": (item.get("departments") or [])[:4],
        }

    def doc_labels(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        return [str(item.get("label") or item.get("id")) for item in items[:12] if isinstance(item, dict) and (item.get("label") or item.get("id"))]

    def compact_department(items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            return []
        return [pick(item, ["id", "label", "status", "stage", "department", "taskKey"]) for item in items[:8] if isinstance(item, dict)]

    def department_labels(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        return [str(item.get("label") or item.get("department") or item.get("id")) for item in items[:8] if isinstance(item, dict) and (item.get("label") or item.get("department") or item.get("id"))]

    decision = result.get("decisionEngine") or {}
    decision_result = decision.get("result") or {}
    slots = result.get("slots") or {}
    business = slots.get("business") or {}
    graph = result.get("requirementGraph") or {}
    document_plan = graph.get("documentPlan") or {}
    department_plan = graph.get("departmentPlan") or {}
    external = result.get("externalChecks") or {}
    building = (external.get("buildingLedger") or {})
    building_summary = building.get("summary") or {}
    compact_decision = {
        "status": decision.get("status"),
        "mode": decision.get("mode"),
        "reason": decision.get("reason", ""),
    }
    if isinstance(decision_result, dict):
        compact_decision["input"] = decision_result.get("input")
        compact_decision["addressDetail"] = decision_result.get("addressDetail")
        compact_decision["recommendedRoutes"] = [compact_route(route) for route in decision_result.get("recommendedRoutes", [])[:5]]
        compact_decision["attentionRoutes"] = [compact_route(route) for route in decision_result.get("attentionRoutes", [])[:5]]
        compact_decision["blockedRoutes"] = [compact_route(route) for route in decision_result.get("blockedRoutes", [])[:5]]
        compact_decision["legalBasis"] = first_items(decision_result.get("legalBasis", []), 8)

    selected_scenario = result.get("scenarioPlan", {}).get("selectedScenario") or {}
    compact_slots = {
        "intent": slots.get("intent"),
        "address": slots.get("address"),
        "business": {
            "concept": business.get("concept"),
            "requestedType": business.get("requestedType"),
            "candidateTypes": business.get("candidateTypes"),
            "liquorSales": business.get("liquorSales"),
            "salesItems": business.get("salesItems"),
            "takeoverOrExistingBusiness": business.get("takeoverOrExistingBusiness"),
        },
        "space": slots.get("space"),
        "facility": slots.get("facility"),
        "documents": slots.get("documents"),
    }
    compact_missing = {
        "requiredNow": [compact_question(item) for item in (result.get("missingInfo", {}).get("requiredNow") or [])[:5]],
        "recommendedNext": [compact_question(item) for item in (result.get("missingInfo", {}).get("recommendedNext") or [])[:5]],
        "later": [compact_question(item) for item in (result.get("missingInfo", {}).get("later") or [])[:5]],
    }
    compact_graph = {
        "scope": graph.get("scope"),
        "activatedActions": [pick(item, ["id", "label", "status"]) for item in graph.get("activatedActions", [])[:10]],
        "missingInputs": [pick(item, ["id", "requiredBy"]) for item in graph.get("missingInputs", [])[:10]],
        "procedurePlan": [compact_procedure(item) for item in graph.get("procedurePlan", [])[:10]],
        "documentPlan": {
            "requiredForSubmission": doc_labels(document_plan.get("requiredForSubmission")),
            "conditional": doc_labels(document_plan.get("conditional")),
            "later": doc_labels(document_plan.get("later"))[:8],
        },
        "departmentPlan": {
            "primary": department_labels(department_plan.get("primary")),
            "conditional": department_labels(department_plan.get("conditional")),
            "later": department_labels(department_plan.get("later")),
        },
    }
    compact_external = {
        "status": external.get("status"),
        "addressForApi": external.get("addressForApi"),
        "buildingLedger": {
            "status": building.get("status"),
            "roadAddr": building.get("roadAddr"),
            "jibunAddr": building.get("jibunAddr"),
            "summary": {
                "mainPurpsCdNm": building_summary.get("mainPurpsCdNm"),
                "etcPurps": building_summary.get("etcPurps"),
                "floorUses": building_summary.get("floorUses", [])[:12],
                "landZones": building_summary.get("landZones", [])[:8],
            },
        },
        "pastBusinessLookup": external.get("pastBusinessLookup"),
    }

    return {
        "inputText": result.get("inputText"),
        "slots": compact_slots,
        "scenario": pick(selected_scenario, ["id", "title", "nextStage", "decisionModules"]),
        "missingInfo": compact_missing,
        "requirementGraph": compact_graph,
        "apiPlan": pick(result.get("apiPlan", {}), ["canRunAddressApi", "canRunBuildingLedgerApi", "canRunPastBusinessLookup", "canRunDecisionEngine", "skipReason"]),
        "externalChecks": compact_external,
        "decisionEngine": compact_decision,
        "currentState": {
            "possibleNow": (result.get("currentState", {}).get("possibleNow") or [])[:5],
            "blockedOrUncertain": (result.get("currentState", {}).get("blockedOrUncertain") or [])[:5],
        },
    }


def build_ai_judgement_prompt(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "system": AI_JUDGEMENT_SYSTEM_PROMPT,
        "user": {
            "task": "허가온 최종 판단 JSON을 생성하라.",
            "schemaVersion": SCHEMA_VERSION,
            "requiredShape": {
                "schemaVersion": SCHEMA_VERSION,
                "decisionStatus": "needs_user_input | needs_api_verification | ready_for_final_guidance",
                "confidence": "low | medium | high",
                "summary": "한 문장 요약",
                "intentSummary": {"intent": "string", "scope": "string", "actions": ["string"]},
                "canSayNow": ["string"],
                "cannotConfirmYet": ["string"],
                "questionsToAsk": [{"id": "string", "question": "string", "reason": "string"}],
                "apiChecks": {"buildingLedger": "string", "pastBusinessLookup": "string", "decisionEngine": "string"},
                "documentSummary": {"required": ["string"], "conditional": ["string"], "later": ["string"]},
                "departmentSummary": {"primary": ["string"], "conditional": ["string"]},
                "finalResponseDraft": "사용자에게 바로 보여줄 한국어 안내 초안",
            },
            "context": compact_for_ai(result),
        },
    }


QUESTION_LABELS: dict[str, tuple[str, str]] = {
    "business_type": ("확인할 업종을 알려주세요.", "업종별 제출서류와 건축물 용도 기준이 달라집니다."),
    "base_address": ("사업장 도로명/지번 주소를 알려주세요.", "건축물대장, 담당 부서, 동일 장소 이력 조회에 필요합니다."),
    "floor_unit": ("층과 호수를 알려주세요.", "층별 용도, 전유부, 소방완비증명서, 동일 장소 매칭에 필요합니다."),
    "area": ("영업장 면적을 알려주세요.", "소방완비증명서와 일부 업종 기준 판단에 필요합니다."),
    "liquor_sales": ("주류를 판매할 계획이 있나요?", "휴게음식점/제과점/일반음식점 경로를 가르는 핵심 조건입니다."),
    "signboard_type": ("설치할 간판 종류를 알려주세요.", "벽면간판, 돌출간판, 입간판 등에 따라 허가/신고 기준이 달라집니다."),
    "signboard_size": ("간판의 대략적인 크기를 알려주세요.", "간판 크기와 설치 위치에 따라 허가/신고/심의 여부가 달라질 수 있습니다."),
    "signboard_location": ("간판 설치 위치를 알려주세요.", "건물 외벽, 돌출, 지주 등 위치에 따라 확인 항목이 달라집니다."),
    "outdoor_location": ("외부 테이블을 둘 곳이 보도/도로인지 사유지인지 알려주세요.", "도로점용 또는 사용권한 확인에 필요합니다."),
    "outdoor_area": ("외부 테이블 수나 사용 면적을 알려주세요.", "도로점용/외부공간 사용 검토에 필요합니다."),
    "owner_consent": ("건물주 또는 관리인 승낙을 받았나요?", "간판과 외부공간 사용 서류에 필요할 수 있습니다."),
}


def labels(items: list[dict[str, Any]], key: str = "label") -> list[str]:
    return [str(item.get(key)) for item in items if item.get(key)]


def graph_missing_questions(result: dict[str, Any]) -> list[dict[str, str]]:
    questions = []
    seen: set[str] = set()
    for item in result.get("requirementGraph", {}).get("missingInputs", []):
        input_id = item.get("id")
        if not input_id or input_id in seen:
            continue
        seen.add(input_id)
        question, reason = QUESTION_LABELS.get(input_id, (f"{input_id} 정보를 알려주세요.", item.get("reason", "")))
        questions.append({"id": input_id, "question": question, "reason": reason})
    return questions


def status_from_context(result: dict[str, Any]) -> str:
    if result.get("requirementGraph", {}).get("missingInputs"):
        return "needs_user_input"
    api_plan = result.get("apiPlan", {})
    if api_plan.get("canRunBuildingLedgerApi") or api_plan.get("canRunDecisionEngine") or api_plan.get("canRunPastBusinessLookup"):
        decision = result.get("decisionEngine") or {}
        external = result.get("externalChecks") or {}
        building = (external.get("buildingLedger") or {}).get("status")
        if decision.get("status") not in {"ok", "skipped"}:
            return "needs_api_verification"
        if api_plan.get("canRunBuildingLedgerApi") and building not in {"ok", "skipped"}:
            return "needs_api_verification"
    return "ready_for_final_guidance"


def rule_based_ai_judgement(result: dict[str, Any]) -> dict[str, Any]:
    graph = result.get("requirementGraph", {})
    document_plan = graph.get("documentPlan", {})
    department_plan = graph.get("departmentPlan", {})
    actions = graph.get("activatedActions", [])
    status = status_from_context(result)
    questions = graph_missing_questions(result)
    current_state = result.get("currentState", {})
    decision = result.get("decisionEngine") or {}
    external = result.get("externalChecks") or {}
    required_docs = labels(document_plan.get("requiredForSubmission", []))
    conditional_docs = labels(document_plan.get("conditional", []))
    later_docs = labels(document_plan.get("later", []))
    primary_departments = labels(department_plan.get("primary", []))
    conditional_departments = labels(department_plan.get("conditional", []))

    if status == "needs_user_input":
        summary = "현재 입력만으로 1차 분류와 서류 후보는 만들 수 있지만, 최종 안내를 위해 추가 정보가 필요합니다."
    elif status == "needs_api_verification":
        summary = "필수 정보는 모였고, 건축물대장/API 검증 결과를 확인해야 최종 가능성을 말할 수 있습니다."
    else:
        summary = "현재 정보와 그래프 기준으로 최종 안내 초안을 만들 수 있습니다."

    response_lines = [
        summary,
        f"분류: {result.get('slots', {}).get('intent')} / {graph.get('scope')}",
    ]
    if required_docs:
        response_lines.append("필요 서류: " + ", ".join(required_docs))
    if conditional_docs:
        response_lines.append("조건부 서류: " + ", ".join(conditional_docs))
    if primary_departments:
        response_lines.append("문의 부서: " + ", ".join(primary_departments))
    if questions:
        response_lines.append("추가로 필요한 정보: " + ", ".join(question["id"] for question in questions))

    return {
        "schemaVersion": SCHEMA_VERSION,
        "decisionStatus": status,
        "confidence": "high" if status == "ready_for_final_guidance" else "medium",
        "summary": summary,
        "intentSummary": {
            "intent": result.get("slots", {}).get("intent"),
            "scope": graph.get("scope"),
            "actions": [item.get("id") for item in actions],
        },
        "canSayNow": current_state.get("possibleNow", []),
        "cannotConfirmYet": current_state.get("blockedOrUncertain", []),
        "questionsToAsk": questions,
        "apiChecks": {
            "buildingLedger": str((external.get("buildingLedger") or {}).get("status") or "not_run"),
            "pastBusinessLookup": str((external.get("pastBusinessLookup") or {}).get("status") or "not_run"),
            "decisionEngine": str(decision.get("status") or "not_run"),
        },
        "documentSummary": {
            "required": required_docs,
            "conditional": conditional_docs,
            "later": later_docs,
        },
        "departmentSummary": {
            "primary": primary_departments,
            "conditional": conditional_departments,
        },
        "finalResponseDraft": "\n".join(response_lines),
    }


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    return json.loads(stripped)


def openai_ai_judgement(result: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIJudgementProviderUnavailable("OPENAI_API_KEY is not set.")
    model = os.getenv("HEOGAON_AI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = build_ai_judgement_prompt(result)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": json.dumps(prompt["user"], ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {message}") from exc
    content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    judgement = parse_json_object(content)
    judgement.setdefault("schemaVersion", SCHEMA_VERSION)
    return judgement


def gms_ai_judgement(result: dict[str, Any]) -> dict[str, Any]:
    prompt = build_ai_judgement_prompt(result)
    judgement = gms_chat_json(
        system_prompt=prompt["system"],
        user_payload=prompt["user"],
        temperature=0.1,
        max_output_tokens=5600,
        timeout=60,
    )
    judgement.pop("_gmsMeta", None)
    judgement.setdefault("schemaVersion", SCHEMA_VERSION)
    return judgement


def run_ai_judgement(
    result: dict[str, Any],
    provider: str = "rule",
    fallback_to_rule: bool = True,
) -> dict[str, Any]:
    provider = (provider or "rule").lower()
    meta = {"requestedProvider": provider, "provider": provider, "fallbackUsed": False, "fallbackReason": ""}

    try:
        if provider == "rule":
            judgement = rule_based_ai_judgement(result)
        elif provider == "openai":
            judgement = openai_ai_judgement(result)
        elif provider == "gms":
            judgement = gms_ai_judgement(result)
        else:
            raise ValueError(f"Unknown AI judgement provider: {provider}")
    except Exception as exc:
        if not fallback_to_rule:
            raise
        meta.update({"provider": "rule", "fallbackUsed": True, "fallbackReason": f"{type(exc).__name__}: {exc}"})
        judgement = rule_based_ai_judgement(result)

    return {
        "status": "ok",
        "mode": "ai_first_with_rule_fallback",
        "meta": meta,
        "judgement": judgement,
        "prompt": build_ai_judgement_prompt(result) if provider in {"gms", "openai"} else None,
    }
