from __future__ import annotations

from typing import Any


AI_GUIDANCE_SYSTEM_PROMPT = """
너는 허가온의 최종 안내 AI다.
사용자에게 직접 보이는 답변을 작성하되, 반드시 제공된 structured context만 근거로 삼는다.

역할:
1. intent, scenario, 현재 상태, API 가능 여부, 제출 서류, 부족 정보, decision/graph 근거를 종합해 안내한다.
2. 법령이나 API 결과가 없는 내용을 확정처럼 말하지 않는다.
3. 사업장 전체 주소는 도로명/지번 주소와 층/호수를 포함한다. 기본 주소만 없어도 가능한 1차 안내는 먼저 하고, 층/호가 필요한 검증은 별도로 구분한다.
4. 질문은 무조건 1개로 제한하지 않는다. 다만 지금 단계에서 판단을 전진시키는 필수 질문만 묶어서 물어본다.
5. 사용자가 “간판만”, “가게 앞 테이블”, “기존 업소 인수”, “서류 준비”처럼 창업이 아닌 목적을 말하면 그 scenario에 맞춰 답한다.
6. 답변은 현재 가능한 것, 아직 막힌 것, 다음 입력/행동, 담당 부서/서류 순서 순으로 간단히 정리한다.
7. aiJudgement가 있으면 그 판단 JSON을 우선 사용하고, 세부 근거가 필요할 때 requirementGraph/API 결과를 확인한다.
8. If requirementGraph.schedulePlan exists, mention time-aware priority, official processing duration, blockers, and parallel tracks.
""".strip()


def compact_slots(slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": slots.get("intent"),
        "address": {
            "quality": slots.get("address", {}).get("quality"),
            "raw": slots.get("address", {}).get("raw"),
            "full": slots.get("address", {}).get("full"),
            "lookupAddress": slots.get("address", {}).get("lookupAddress"),
            "detail": slots.get("address", {}).get("detail"),
        },
        "business": {
            "concept": slots.get("business", {}).get("concept"),
            "requestedType": slots.get("business", {}).get("requestedType"),
            "candidateTypes": slots.get("business", {}).get("candidateTypes", []),
            "liquorSales": slots.get("business", {}).get("liquorSales"),
            "salesItems": slots.get("business", {}).get("salesItems", []),
            "candidateRoutes": slots.get("business", {}).get("candidateRoutes", []),
        },
        "space": {
            "areaM2": slots.get("space", {}).get("areaM2"),
            "areaPyeong": slots.get("space", {}).get("areaPyeong"),
            "sourceText": slots.get("space", {}).get("sourceText"),
        },
        "facility": slots.get("facility", {}),
        "documents": slots.get("documents", {}),
    }


def build_question_strategy(missing_info: dict[str, Any]) -> dict[str, Any]:
    required = missing_info.get("requiredNow", [])
    recommended = missing_info.get("recommendedNext", [])
    return {
        "askPolicy": "필수 정보가 여러 개면 한 번에 묶어서 묻고, 선택 정보는 뒤 단계로 미룬다.",
        "requiredQuestionIds": [item.get("id") for item in required],
        "recommendedLaterIds": [item.get("id") for item in recommended],
        "maxQuestionBundle": 4,
    }


def build_answer_plan(result: dict[str, Any]) -> dict[str, Any]:
    scenario = result.get("scenarioPlan", {}).get("selectedScenario", {})
    current_state = result.get("currentState", {})
    return {
        "tone": "친절하지만 확정/불확정을 명확히 구분",
        "scenarioTitle": scenario.get("title"),
        "sections": [
            "현재 의도 분류",
            "지금 바로 말할 수 있는 판단",
            "최종 판단을 위해 막힌 정보",
            "다음에 받을 질문",
            "서류/부서/제출 순서",
            "Schedule priority and parallel tracks",
        ],
        "mustMention": {
            "possibleNow": current_state.get("possibleNow", []),
            "blockedOrUncertain": current_state.get("blockedOrUncertain", []),
            "documentPlan": result.get("requirementGraph", {}).get("documentPlan", {}),
            "departmentPlan": result.get("requirementGraph", {}).get("departmentPlan", {}),
            "schedulePlan": result.get("requirementGraph", {}).get("schedulePlan", {}),
        },
    }


def build_ai_guidance_packet(result: dict[str, Any]) -> dict[str, Any]:
    decision_engine = result.get("decisionEngine", {"status": "not_requested"})
    question_strategy = build_question_strategy(result.get("missingInfo", {}))
    question_strategy["graphRequiredInputIds"] = [
        item.get("id") for item in result.get("requirementGraph", {}).get("missingInputs", [])
    ]
    context = {
        "inputText": result.get("inputText"),
        "scenario": result.get("scenarioPlan", {}).get("selectedScenario"),
        "slots": compact_slots(result.get("slots", {})),
        "preliminaryDiagnosis": result.get("preliminaryDiagnosis"),
        "missingInfo": result.get("missingInfo"),
        "requirementGraph": result.get("requirementGraph"),
        "apiPlan": result.get("apiPlan"),
        "externalChecks": result.get("externalChecks"),
        "aiJudgement": result.get("aiJudgement"),
        "inquiryPackage": result.get("inquiryPackage"),
        "currentState": result.get("currentState"),
        "decisionEngine": decision_engine,
    }
    return {
        "mode": "llm_final_guidance",
        "status": "ready_for_llm",
        "systemPrompt": AI_GUIDANCE_SYSTEM_PROMPT,
        "context": context,
        "questionStrategy": question_strategy,
        "answerPlan": build_answer_plan(result),
        "guardrails": [
            "structured context에 없는 행정 사실은 확정하지 않기",
            "API 미조회 상태와 조회 완료 상태를 분리해서 말하기",
            "사용자 목적이 음식점 창업이 아니면 음식점 판단 플로우로 끌고 가지 않기",
            "최종 행정처분/허가 가능 여부는 담당 기관 확인 필요성을 남기기",
        ],
    }
