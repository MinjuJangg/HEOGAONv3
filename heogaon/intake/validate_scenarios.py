from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


INTAKE_DIR = Path(__file__).resolve().parent
if str(INTAKE_DIR) not in sys.path:
    sys.path.insert(0, str(INTAKE_DIR))

from intake_pipeline import build_intake_result  # noqa: E402


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "mapo_cafe_full_opening",
        "title": "마포구 카페 창업",
        "initialQuery": "마포구 망원동에서 15평 카페를 창업하고 싶어요. 디저트 팔고 간판도 달 거예요.",
        "followUp": "사업장 전체 주소는 서울특별시 마포구 포은로 63, 1층 101호이고 주류는 안 팔아요. 벽면간판 가로 3m 세로 1m이고 건물주 승낙 받았어요.",
        "expected": {
            "intent": "food_business_precheck",
            "scope": "full_opening",
            "actions": ["open_food_business", "check_building_use", "check_same_place_history", "install_signboard"],
            "requiredDocs": ["food_business_report", "hygiene_training", "health_certificate", "lease_contract", "id_card", "signboard_application"],
        },
    },
    {
        "id": "gangnam_restaurant_road_occupancy",
        "title": "강남구 일반음식점 + 도로점용",
        "initialQuery": "강남구 역삼동에서 40평 일반음식점을 열고 주류도 팔고 가게 앞 보도에 테이블 4개를 두고 싶어요.",
        "followUp": "사업장 전체 주소는 서울특별시 강남구 테헤란로 152, 1층 101호입니다. 보도 위 테이블 4개이고 건물주 승낙 받았어요.",
        "expected": {
            "intent": "food_business_precheck",
            "scope": "full_opening",
            "actions": ["open_food_business", "check_building_use", "check_same_place_history", "use_outdoor_space"],
            "requiredDocs": ["food_business_report", "health_certificate", "outdoor_space_materials", "outdoor_owner_consent"],
        },
    },
    {
        "id": "songpa_signboard_only",
        "title": "송파구 간판 설치",
        "initialQuery": "송파구에서 이미 운영 중인 매장에 돌출간판만 설치하고 싶어요.",
        "followUp": "주소는 서울특별시 송파구 올림픽로 300, 1층이고 돌출간판 가로 2m 세로 0.8m, 건물주 승낙 받았어요.",
        "expected": {
            "intent": "signboard_permit_check",
            "scope": "specific_check",
            "actions": ["install_signboard"],
            "requiredDocs": ["signboard_application", "signboard_owner_consent", "signboard_photo_design"],
            "forbiddenDocs": ["food_business_report", "hygiene_training", "health_certificate"],
        },
    },
    {
        "id": "mapo_existing_cafe_add_liquor",
        "title": "마포구 기존 카페 주류 추가",
        "initialQuery": "마포구에서 이미 운영 중인 카페인데 맥주랑 와인을 추가로 팔고 싶어요.",
        "followUp": "사업장 전체 주소는 서울특별시 마포구 월드컵로 29, 1층 101호입니다. 현재 휴게음식점이고 주류 추가 예정이에요.",
        "expected": {
            "intent": "business_change_check",
            "scope": "partial_change",
            "actions": ["change_food_business"],
            "requiredDocs": ["building_ledger_result"],
        },
    },
    {
        "id": "jongno_building_use_check",
        "title": "종로구 건축물대장 용도 확인",
        "initialQuery": "종로구에서 일반음식점 가능한 건축물 용도인지 건축물대장만 확인하고 싶어요.",
        "followUp": "주소는 서울특별시 종로구 종로 1, 2층 201호입니다.",
        "expected": {
            "intent": "building_use_check",
            "scope": "specific_check",
            "actions": ["check_building_use"],
            "requiredDocs": ["building_ledger_result"],
        },
    },
    {
        "id": "seocho_document_readiness",
        "title": "서초구 서류 준비상태 점검",
        "initialQuery": "서초구에서 일반음식점 영업신고 서류가 어디까지 준비됐는지 보고 싶어요. 보건증은 있어요.",
        "followUp": "주소는 서울특별시 서초구 서초대로 396, 1층 101호이고 위생교육 수료증도 받았고 임대차계약서 있어요.",
        "expected": {
            "intent": "document_readiness_check",
            "scope": "document_status",
            "actions": ["document_readiness", "open_food_business"],
            "preparedDocs": ["healthCertificate", "hygieneTraining", "leaseContract"],
        },
    },
    {
        "id": "yeongdeungpo_takeover_history",
        "title": "영등포구 기존 업소 인수 이력 확인",
        "initialQuery": "영등포구 기존 일반음식점을 인수하려는데 같은 장소 행정처분 이력이 있었는지 알고 싶어요.",
        "followUp": "주소는 서울특별시 영등포구 여의대로 24, 1층 102호이고 일반음식점 인수 예정입니다.",
        "expected": {
            "intent": "takeover_history_check",
            "scope": "takeover_or_history",
            "actions": ["check_same_place_history"],
            "requiredDocs": ["same_place_history_result"],
        },
    },
    {
        "id": "yongsan_bakery_second_floor",
        "title": "용산구 2층 베이커리 창업",
        "initialQuery": "용산구 이태원동에서 120㎡ 베이커리 창업하고 싶어요. 2층이고 간판도 달 예정이에요.",
        "followUp": "사업장 전체 주소는 서울특별시 용산구 이태원로 179, 2층 201호입니다. 주류는 안 팔고 전면간판 가로 4m 세로 1m, 건물주 승낙 받았어요.",
        "expected": {
            "intent": "food_business_precheck",
            "scope": "full_opening",
            "actions": ["open_food_business", "check_building_use", "check_same_place_history", "install_signboard"],
            "requiredDocs": ["food_business_report", "fire_safety_certificate", "signboard_application"],
        },
    },
    {
        "id": "seongdong_basement_cafe",
        "title": "성동구 지하 카페 창업",
        "initialQuery": "성동구에서 지하 1층 70㎡ 카페를 열고 싶어요. 주류는 안 팔아요.",
        "followUp": "사업장 전체 주소는 서울특별시 성동구 왕십리로 222, 지하 1층 101호입니다.",
        "expected": {
            "intent": "food_business_precheck",
            "scope": "full_opening",
            "actions": ["open_food_business", "check_building_use", "check_same_place_history"],
            "requiredDocs": ["food_business_report", "fire_safety_certificate"],
        },
    },
    {
        "id": "gwanak_outdoor_only",
        "title": "관악구 외부 테이블만",
        "initialQuery": "관악구에서 운영 중인 카페인데 가게 앞 테라스에 테이블만 두고 싶어요.",
        "followUp": "주소는 서울특별시 관악구 관악로 1, 1층이고 테라스 사유지에 테이블 3개, 건물주 승낙 받았어요.",
        "expected": {
            "intent": "outdoor_space_permit_check",
            "scope": "specific_check",
            "actions": ["use_outdoor_space"],
            "requiredDocs": ["outdoor_space_materials", "outdoor_owner_consent"],
            "forbiddenDocs": ["food_business_report", "hygiene_training", "health_certificate"],
        },
    },
]


def document_ids(plan: dict[str, Any]) -> set[str]:
    docs = []
    for key in ["requiredForSubmission", "conditional", "later", "notRequiredByCurrentInputs"]:
        docs.extend(plan.get(key, []))
    return {item.get("id") for item in docs}


def active_action_ids(graph: dict[str, Any]) -> set[str]:
    return {item.get("id") for item in graph.get("activatedActions", [])}


def prepared_doc_ids(result: dict[str, Any]) -> set[str]:
    return {key for key, value in result.get("slots", {}).get("documents", {}).items() if value == "prepared"}


def api_status(result: dict[str, Any], api_was_requested: bool, api_env_ready: bool) -> dict[str, Any]:
    external = result.get("externalChecks")
    if "decisionEngine" in result:
        decision = result["decisionEngine"]
        return {
            "requested": api_was_requested,
            "envReady": api_env_ready,
            "status": decision.get("status"),
            "reason": decision.get("reason", ""),
            "externalChecks": external,
        }
    api_plan = result.get("apiPlan", {})
    if (api_plan.get("canRunDecisionEngine") or api_plan.get("canRunBuildingLedgerApi")) and not api_env_ready:
        return {"requested": False, "envReady": False, "status": "not_run_env_missing", "reason": "JUSO_API_KEY/DATA_GO_KR_SERVICE_KEY not set", "externalChecks": external}
    return {"requested": False, "envReady": api_env_ready, "status": "not_needed_or_not_ready", "reason": api_plan.get("skipReason", ""), "externalChecks": external}


def validate_case(case: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    expected = case["expected"]
    graph = result["requirementGraph"]
    docs = document_ids(graph["documentPlan"])
    actions = active_action_ids(graph)
    prepared = prepared_doc_ids(result)
    checks = [
        {"name": "intent", "ok": result["slots"]["intent"] == expected["intent"], "actual": result["slots"]["intent"], "expected": expected["intent"]},
        {"name": "scope", "ok": graph["scope"] == expected["scope"], "actual": graph["scope"], "expected": expected["scope"]},
        {"name": "actions", "ok": set(expected.get("actions", [])).issubset(actions), "actual": sorted(actions), "expected": expected.get("actions", [])},
        {"name": "requiredDocs", "ok": set(expected.get("requiredDocs", [])).issubset(docs), "actual": sorted(docs), "expected": expected.get("requiredDocs", [])},
        {"name": "aiJudgement", "ok": result.get("aiJudgement", {}).get("status") == "ok", "actual": result.get("aiJudgement", {}).get("status"), "expected": "ok"},
        {"name": "inquiryPackage", "ok": result.get("inquiryPackage", {}).get("status") == "ok", "actual": result.get("inquiryPackage", {}).get("status"), "expected": "ok"},
        {"name": "contacts", "ok": bool(result.get("inquiryPackage", {}).get("contacts")), "actual": len(result.get("inquiryPackage", {}).get("contacts", [])), "expected": ">=1"},
        {"name": "scripts", "ok": bool(result.get("inquiryPackage", {}).get("scripts", {}).get("scripts")), "actual": len(result.get("inquiryPackage", {}).get("scripts", {}).get("scripts", [])), "expected": ">=1"},
    ]
    if expected.get("forbiddenDocs"):
        forbidden = set(expected["forbiddenDocs"])
        checks.append({"name": "forbiddenDocsAbsent", "ok": not forbidden.intersection(docs), "actual": sorted(forbidden.intersection(docs)), "expected": []})
    if expected.get("preparedDocs"):
        checks.append({"name": "preparedDocs", "ok": set(expected["preparedDocs"]).issubset(prepared), "actual": sorted(prepared), "expected": expected["preparedDocs"]})
    return checks


def summarize_result(case: dict[str, Any], initial: dict[str, Any], completed: dict[str, Any], api_was_requested: bool, api_env_ready: bool) -> dict[str, Any]:
    graph = completed["requirementGraph"]
    document_plan = graph["documentPlan"]
    checks = validate_case(case, completed)
    return {
        "id": case["id"],
        "title": case["title"],
        "initialQuery": case["initialQuery"],
        "followUp": case["followUp"],
        "initial": {
            "intent": initial["slots"]["intent"],
            "scope": initial["requirementGraph"]["scope"],
            "requiredNow": [item["id"] for item in initial["missingInfo"]["requiredNow"]],
            "graphMissingInputs": [item["id"] for item in initial["requirementGraph"]["missingInputs"]],
        },
        "completed": {
            "intent": completed["slots"]["intent"],
            "scope": graph["scope"],
            "candidateTypes": completed["slots"]["business"].get("candidateTypes", []),
            "actions": graph["activatedActions"],
            "graphMissingInputs": [item["id"] for item in graph["missingInputs"]],
            "requiredDocs": [item["label"] for item in document_plan["requiredForSubmission"]],
            "conditionalDocs": [{"label": item["label"], "status": item["status"], "missingInputs": item.get("missingInputs", [])} for item in document_plan["conditional"]],
            "laterDocs": [item["label"] for item in document_plan["later"]],
            "departments": graph["departmentPlan"],
            "preparedDocs": sorted(prepared_doc_ids(completed)),
            "aiJudgement": {
                "provider": completed.get("aiJudgement", {}).get("meta", {}).get("provider"),
                "fallbackUsed": completed.get("aiJudgement", {}).get("meta", {}).get("fallbackUsed"),
                "decisionStatus": completed.get("aiJudgement", {}).get("judgement", {}).get("decisionStatus"),
                "questionIds": [
                    item.get("id")
                    for item in completed.get("aiJudgement", {}).get("judgement", {}).get("questionsToAsk", [])
                ],
            },
            "inquiryPackage": {
                "district": completed.get("inquiryPackage", {}).get("district"),
                "contactCount": len(completed.get("inquiryPackage", {}).get("contacts", [])),
                "contacts": [
                    {
                        "taskKey": item.get("taskKey"),
                        "departmentName": item.get("departmentName"),
                        "phone": item.get("phone"),
                        "sourceUrl": item.get("sourceUrl"),
                    }
                    for item in completed.get("inquiryPackage", {}).get("contacts", [])[:4]
                ],
                "scriptProvider": completed.get("inquiryPackage", {}).get("scripts", {}).get("meta", {}).get("provider"),
                "scriptFallbackUsed": completed.get("inquiryPackage", {}).get("scripts", {}).get("meta", {}).get("fallbackUsed"),
            },
            "api": api_status(completed, api_was_requested, api_env_ready),
        },
        "validation": {
            "ok": all(check["ok"] for check in checks),
            "checks": checks,
        },
    }


def run_validation(api_mode: str, judgement_provider: str, inquiry_provider: str) -> dict[str, Any]:
    api_env_ready = bool(os.getenv("JUSO_API_KEY")) and bool(os.getenv("DATA_GO_KR_SERVICE_KEY"))
    summaries = []
    for case in SCENARIOS:
        initial = build_intake_result(
            case["initialQuery"],
            run_decision=False,
            judgement_provider=judgement_provider,
            inquiry_provider=inquiry_provider,
        )
        completed_text = f"{case['initialQuery']} {case['followUp']}"
        should_use_api = api_mode == "on" or (api_mode == "auto" and api_env_ready)
        completed = build_intake_result(
            completed_text,
            run_decision=should_use_api,
            judgement_provider=judgement_provider,
            inquiry_provider=inquiry_provider,
        )
        summaries.append(summarize_result(case, initial, completed, should_use_api, api_env_ready))
    return {
        "scenarioCount": len(SCENARIOS),
        "apiMode": api_mode,
        "judgementProvider": judgement_provider,
        "inquiryProvider": inquiry_provider,
        "apiEnvReady": api_env_ready,
        "passed": sum(1 for item in summaries if item["validation"]["ok"]),
        "failed": [item["id"] for item in summaries if not item["validation"]["ok"]],
        "cases": summaries,
    }


def print_human_report(report: dict[str, Any]) -> None:
    print(f"HEOGAON scenario validation: {report['passed']}/{report['scenarioCount']} passed")
    print(f"API mode={report['apiMode']}, apiEnvReady={report['apiEnvReady']}, judgementProvider={report['judgementProvider']}, inquiryProvider={report['inquiryProvider']}")
    print()
    for item in report["cases"]:
        mark = "PASS" if item["validation"]["ok"] else "FAIL"
        completed = item["completed"]
        print(f"[{mark}] {item['id']} - {item['title']}")
        print(f"  initial intent/scope: {item['initial']['intent']} / {item['initial']['scope']}")
        print(f"  completed intent/scope: {completed['intent']} / {completed['scope']}")
        print(f"  initial missing: {', '.join(item['initial']['graphMissingInputs']) or '없음'}")
        print(f"  completed missing: {', '.join(completed['graphMissingInputs']) or '없음'}")
        print(f"  actions: {', '.join(action['id'] + ':' + action['status'] for action in completed['actions'])}")
        print(f"  docs: {', '.join(completed['requiredDocs']) or '없음'}")
        if completed["conditionalDocs"]:
            print("  conditional: " + ", ".join(doc["label"] for doc in completed["conditionalDocs"]))
        judgement = completed.get("aiJudgement") or {}
        print(
            "  aiJudgement: "
            f"provider={judgement.get('provider')}, "
            f"fallback={judgement.get('fallbackUsed')}, "
            f"status={judgement.get('decisionStatus')}, "
            f"questions={', '.join(judgement.get('questionIds') or []) or '없음'}"
        )
        inquiry = completed.get("inquiryPackage") or {}
        contact_preview = ", ".join(
            f"{contact.get('taskKey')}:{contact.get('departmentName')}"
            for contact in (inquiry.get("contacts") or [])[:3]
        )
        print(
            "  inquiry: "
            f"district={inquiry.get('district')}, "
            f"contacts={inquiry.get('contactCount')}, "
            f"scriptProvider={inquiry.get('scriptProvider')}, "
            f"fallback={inquiry.get('scriptFallbackUsed')}"
        )
        if contact_preview:
            print(f"  contactPreview: {contact_preview}")
        print(f"  api: {completed['api']['status']} {completed['api']['reason']}".rstrip())
        external = completed["api"].get("externalChecks") or {}
        if external:
            building_status = (external.get("buildingLedger") or {}).get("status")
            past_status = (external.get("pastBusinessLookup") or {}).get("status")
            print(f"  externalChecks: building={building_status}, pastBusiness={past_status}")
        failed_checks = [check for check in item["validation"]["checks"] if not check["ok"]]
        for check in failed_checks:
            print(f"  - failed {check['name']}: actual={check['actual']} expected={check['expected']}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate HEOGAON intake scenario routing and requirement graph.")
    parser.add_argument("--api-mode", choices=["auto", "off", "on"], default="auto", help="auto uses APIs only when env keys are set")
    parser.add_argument("--judgement-provider", choices=["rule", "gms", "openai"], default="rule", help="AI judgement provider")
    parser.add_argument("--inquiry-provider", choices=["rule", "gms", "openai"], default="rule", help="Inquiry script provider")
    parser.add_argument("--json", action="store_true", help="print full JSON report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_validation(args.api_mode, args.judgement_provider, args.inquiry_provider)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human_report(report)


if __name__ == "__main__":
    main()
