from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MINJU_ROOT = ROOT.parent
GRAPH_ROOT = MINJU_ROOT / "graph" / "output" / "final_graph"
OLD_EDGES = GRAPH_ROOT / "graph_edges_high_precision.before_all_raw_rechunk.csv"
NEW_EDGES = GRAPH_ROOT / "graph_edges_high_precision.csv"
OUT_JSON = ROOT / "ten_scenario_before_after_comparison.json"
OUT_MD = ROOT / "ten_scenario_before_after_comparison.md"

FLOW_PREDICATES = {"precedes", "triggers", "requires_permit"}
GROUNDING_EDGE_SOURCES = {
    "manual_atomic_rechunk",
    "raw_atomic_rechunk",
    "source_backed_core_flow",
    "source_backed_seed",
    "rule_seed",
}


def load_ten_module() -> Any:
    module_path = ROOT / "extract_ten_full_scenarios.py"
    spec = importlib.util.spec_from_file_location("extract_ten_full_scenarios", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ten = load_ten_module()


def read_edges(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def compact(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def edge_key(edge: dict[str, str]) -> str:
    return f"{edge.get('predicate')}|{edge.get('subject_name')}|{edge.get('object_name')}"


def doc_key(doc: dict[str, str]) -> str:
    return f"{doc.get('subject')}|{doc.get('canonical_object')}"


def prereq_key(item: dict[str, str]) -> str:
    return f"{item.get('subject')}|{item.get('prerequisite')}"


def route_key(route: dict[str, str]) -> str:
    return f"{route.get('subject')}|{route.get('object')}"


def normalize_for_match(text: str) -> str:
    return (text or "").replace(" ", "")


def scenario_terms(scenario: dict[str, Any]) -> set[str]:
    terms = set()
    terms.add(scenario["business_type"])
    terms.update(scenario["permits"])
    terms.update(scenario.get("condition_terms", []))
    terms.update(scenario.get("force_documents", []))
    terms.update(scenario.get("order", []))

    if ten.FOOD_PERMIT in scenario["permits"]:
        terms.update(
            [
                "주소",
                "점포",
                "건물",
                "건축물대장",
                "용도",
                "위반건축물",
                "소유자",
                "관리인",
                "임대차",
                "위생교육",
                "건강진단",
                "영업신고",
                "영업신고증",
                "사업자등록",
                "행정처분",
                "주류",
                "일반음식점",
                "휴게음식점",
                "안전시설",
                "소방",
            ]
        )
    if ten.ROAD_PERMIT in scenario["permits"]:
        terms.update(["도로", "도로점용", "보도", "테라스", "외부 공간", "위치도", "평면도"])
    if ten.AD_PERMIT in scenario["permits"]:
        terms.update(["옥외광고물", "간판", "입간판", "배너", "광고물", "수수료", "허가", "신고증"])
    if ten.SUCCESSION_PERMIT in scenario["permits"]:
        terms.update(["지위승계", "양도", "양수", "기존 음식점", "인수", "기존 업소"])
    if ten.MAIL_ORDER_PERMIT in scenario["permits"]:
        terms.update(["통신판매", "온라인", "사업자등록", "구매안전", "신고증", "등록면허세"])
    return {term for term in terms if term}


def flow_edge_matches(edge: dict[str, str], scenario: dict[str, Any]) -> bool:
    if edge["predicate"] not in FLOW_PREDICATES:
        return False
    if edge["edge_source"] not in GROUNDING_EDGE_SOURCES:
        return False

    subject = edge["subject_name"]
    obj = edge["object_name"]
    blob = normalize_for_match(" ".join([subject, obj, edge.get("condition_text", ""), edge.get("title", "")]))
    terms = scenario_terms(scenario)

    if edge["predicate"] == "requires_permit":
        return subject == scenario["business_type"] or obj in scenario["permits"]
    if edge["predicate"] == "triggers":
        if ten.AD_PERMIT in scenario["permits"]:
            return obj == ten.AD_PERMIT
        if ten.MAIL_ORDER_PERMIT in scenario["permits"]:
            return obj == ten.MAIL_ORDER_PERMIT
        return obj in scenario["permits"] or any(normalize_for_match(term) in blob for term in terms)
    if edge["predicate"] == "precedes":
        if ten.AD_PERMIT in scenario["permits"]:
            return any(normalize_for_match(term) in blob for term in ["옥외광고물", "간판", "입간판", "광고물"])
        if ten.MAIL_ORDER_PERMIT in scenario["permits"]:
            if any(normalize_for_match(term) in blob for term in ["영업신고", "주류", "위생", "건축물", "옥외광고물", "간판"]):
                return False
            return any(normalize_for_match(term) in blob for term in ["사업자등록", "통신판매", "구매안전", "등록면허세"])
        if ten.ROAD_PERMIT in scenario["permits"] and any(normalize_for_match(term) in blob for term in ["도로점용", "도로", "보도", "외부공간"]):
            return True
        if ten.SUCCESSION_PERMIT in scenario["permits"] and any(normalize_for_match(term) in blob for term in ["지위승계", "양도", "양수", "기존업소", "행정처분"]):
            return True
        if ten.FOOD_PERMIT in scenario["permits"]:
            return any(
                normalize_for_match(term) in blob
                for term in [
                    "건축물",
                    "용도",
                    "위반건축물",
                    "위생교육",
                    "건강진단",
                    "영업신고",
                    "영업신고증",
                    "사업자등록",
                    "임대차",
                    "신분증",
                    "안전시설",
                    "주류",
                    "일반음식점",
                    "행정처분",
                ]
            )
    return False


def collect_flow_edges(edges: list[dict[str, str]], scenario: dict[str, Any]) -> list[dict[str, str]]:
    matched = [edge for edge in edges if flow_edge_matches(edge, scenario)]
    seen = set()
    unique = []
    for edge in sorted(matched, key=lambda item: (item["predicate"], item["subject_name"], item["object_name"], item["edge_source"])):
        key = edge_key(edge)
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            {
                "predicate": edge["predicate"],
                "subject": edge["subject_name"],
                "object": edge["object_name"],
                "edge_source": edge["edge_source"],
                "source_title": edge["title"],
                "condition_text": edge["condition_text"],
            }
        )
    return unique


def graph_stats(edges: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "edge_count": len(edges),
        "predicate_counts": dict(Counter(edge["predicate"] for edge in edges)),
        "edge_source_counts": dict(Counter(edge["edge_source"] for edge in edges)),
    }


def run_for_graph(path: Path) -> dict[str, Any]:
    edges = read_edges(path)
    ten.EDGES_PATH = path
    results = ten.build_results()
    by_id = {item["scenario_id"]: item for item in results}
    for scenario in ten.SCENARIOS:
        by_id[scenario["scenario_id"]]["graph_flow_edges"] = collect_flow_edges(edges, scenario)
    return {"path": str(path), "stats": graph_stats(edges), "results": by_id}


def keyset(items: list[dict[str, str]], key_fn: Any) -> set[str]:
    return {key_fn(item) for item in items}


def summarize_result(item: dict[str, Any]) -> dict[str, int]:
    return {
        "required_documents": len(item["required_documents"]),
        "triggered_documents": len(item["triggered_documents"]),
        "conditional_documents": len(item["conditional_documents"]),
        "all_documents": len(item["required_documents"]) + len(item["triggered_documents"]) + len(item["conditional_documents"]),
        "checks_and_risks": len(item["checks_and_risks"]),
        "prerequisites": len(item["prerequisites"]),
        "submission_routes": len(item["submission_routes"]),
        "graph_flow_edges": len(item["graph_flow_edges"]),
        "graph_precedes_edges": sum(1 for edge in item["graph_flow_edges"] if edge["predicate"] == "precedes"),
    }


def diff_items(old_items: list[dict[str, str]], new_items: list[dict[str, str]], key_fn: Any) -> dict[str, list[str]]:
    old_keys = keyset(old_items, key_fn)
    new_keys = keyset(new_items, key_fn)
    return {"added": sorted(new_keys - old_keys), "removed": sorted(old_keys - new_keys)}


def scenario_comparison(old_item: dict[str, Any], new_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": new_item["scenario_id"],
        "input": new_item["input"],
        "old_counts": summarize_result(old_item),
        "new_counts": summarize_result(new_item),
        "diffs": {
            "required_documents": diff_items(old_item["required_documents"], new_item["required_documents"], doc_key),
            "triggered_documents": diff_items(old_item["triggered_documents"], new_item["triggered_documents"], doc_key),
            "conditional_documents": diff_items(old_item["conditional_documents"], new_item["conditional_documents"], doc_key),
            "checks_and_risks": diff_items(old_item["checks_and_risks"], new_item["checks_and_risks"], doc_key),
            "prerequisites": diff_items(old_item["prerequisites"], new_item["prerequisites"], prereq_key),
            "submission_routes": diff_items(old_item["submission_routes"], new_item["submission_routes"], route_key),
            "graph_flow_edges": diff_items(old_item["graph_flow_edges"], new_item["graph_flow_edges"], edge_key),
        },
        "current": {
            "permits": new_item["permits"],
            "required_documents": new_item["required_documents"],
            "triggered_documents": new_item["triggered_documents"],
            "conditional_documents": new_item["conditional_documents"],
            "checks_and_risks": new_item["checks_and_risks"],
            "prerequisites": new_item["prerequisites"],
            "submission_routes": new_item["submission_routes"],
            "graph_flow_edges": new_item["graph_flow_edges"],
        },
    }


def verdict(row: dict[str, Any]) -> str:
    counts = row["new_counts"]
    if counts["all_documents"] == 0:
        return "문서 부족"
    if counts["submission_routes"] == 0:
        return "부서 기능 부족"
    if counts["graph_precedes_edges"] == 0:
        return "순서 edge 부족"
    if counts["prerequisites"] == 0 and any(term in row["input"] for term in ["소방", "LPG", "도로", "간판", "지위승계"]):
        return "선행조건 추가 확인"
    return "데모 답변 가능"


def format_delta(old: int, new: int) -> str:
    delta = new - old
    sign = "+" if delta >= 0 else ""
    return f"{old} -> {new} ({sign}{delta})"


def list_added(lines: list[str], title: str, values: list[str], limit: int = 8) -> None:
    if not values:
        return
    lines.append(f"- {title}: " + ", ".join(values[:limit]) + (" ..." if len(values) > limit else ""))


def write_markdown(payload: dict[str, Any]) -> None:
    old_stats = payload["old"]["stats"]
    new_stats = payload["new"]["stats"]
    rows = payload["scenario_comparisons"]

    lines = [
        "# Ten Scenario Before/After Graph Comparison",
        "",
        "같은 10개 시나리오를 재청킹 전 그래프와 현재 최종 그래프에 각각 태워서 비교했습니다.",
        "비교 기준은 그래프 CSV의 구조화 edge입니다. 지역 실제 과명 매핑 DB는 별도이고, 여기서는 그래프의 기능부서/서류/순서/선행조건을 검증합니다.",
        "",
        "## Graph-Wide Delta",
        "",
        f"- old graph: `{OLD_EDGES.name}`",
        f"- new graph: `{NEW_EDGES.name}`",
        f"- total edges: {format_delta(old_stats['edge_count'], new_stats['edge_count'])}",
        "",
        "| predicate | old | new | delta |",
        "|---|---:|---:|---:|",
    ]
    predicates = sorted(set(old_stats["predicate_counts"]) | set(new_stats["predicate_counts"]))
    for predicate in predicates:
        old_count = old_stats["predicate_counts"].get(predicate, 0)
        new_count = new_stats["predicate_counts"].get(predicate, 0)
        lines.append(f"| {predicate} | {old_count} | {new_count} | {new_count - old_count:+d} |")

    lines.extend(
        [
            "",
            "## Scenario Summary",
            "",
            "| scenario | 문서 | 부서기능 | 순서edge | 선행조건 | 확인/리스크 | 판정 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in rows:
        old_counts = row["old_counts"]
        new_counts = row["new_counts"]
        lines.append(
            "| {scenario} | {docs} | {routes} | {flows} | {prereq} | {checks} | {verdict} |".format(
                scenario=row["scenario_id"],
                docs=format_delta(old_counts["all_documents"], new_counts["all_documents"]),
                routes=format_delta(old_counts["submission_routes"], new_counts["submission_routes"]),
                flows=format_delta(old_counts["graph_precedes_edges"], new_counts["graph_precedes_edges"]),
                prereq=format_delta(old_counts["prerequisites"], new_counts["prerequisites"]),
                checks=format_delta(old_counts["checks_and_risks"], new_counts["checks_and_risks"]),
                verdict=verdict(row),
            )
        )

    for row in rows:
        current = row["current"]
        diffs = row["diffs"]
        lines.extend(["", f"## {row['scenario_id']} - {row['input']}", ""])
        lines.append("- 필요한 인허가: " + ", ".join(current["permits"]))

        if current["submission_routes"]:
            lines.append("- 그래프 기능부서: " + ", ".join(f"{item['subject']} -> {item['object']}" for item in current["submission_routes"]))
        else:
            lines.append("- 그래프 기능부서: 없음")

        core_docs = current["required_documents"] + current["triggered_documents"]
        if core_docs:
            lines.append("- 현재 필수/조건발동 서류: " + ", ".join(f"{doc['canonical_object']}({doc['subject']})" for doc in core_docs))
        else:
            lines.append("- 현재 필수/조건발동 서류: 없음")

        if current["prerequisites"]:
            lines.append("- 현재 선행조건: " + ", ".join(f"{item['subject']} <- {item['prerequisite']}" for item in current["prerequisites"][:12]))
        else:
            lines.append("- 현재 선행조건: 없음")

        flow_edges = current["graph_flow_edges"]
        if flow_edges:
            lines.append("- 현재 그래프 순서/트리거:")
            for edge in flow_edges[:16]:
                cond = f" / {compact(edge['condition_text'], 80)}" if edge["condition_text"] else ""
                lines.append(f"  - {edge['predicate']}: {edge['subject']} -> {edge['object']} ({edge['edge_source']}){cond}")
            if len(flow_edges) > 16:
                lines.append(f"  - ... {len(flow_edges) - 16}개 더 있음")
        else:
            lines.append("- 현재 그래프 순서/트리거: 없음")

        list_added(lines, "이번 그래프에서 추가된 필수서류", diffs["required_documents"]["added"])
        list_added(lines, "이번 그래프에서 추가된 조건발동서류", diffs["triggered_documents"]["added"])
        list_added(lines, "이번 그래프에서 추가된 확인/리스크", diffs["checks_and_risks"]["added"])
        list_added(lines, "이번 그래프에서 추가된 순서/트리거", diffs["graph_flow_edges"]["added"])

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    old = run_for_graph(OLD_EDGES)
    new = run_for_graph(NEW_EDGES)
    comparisons = []
    for scenario in ten.SCENARIOS:
        sid = scenario["scenario_id"]
        comparisons.append(scenario_comparison(old["results"][sid], new["results"][sid]))

    payload = {
        "old": {"path": old["path"], "stats": old["stats"]},
        "new": {"path": new["path"], "stats": new["stats"]},
        "scenario_comparisons": comparisons,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload)
    print(f"json={OUT_JSON}")
    print(f"markdown={OUT_MD}")
    for row in comparisons:
        print(
            row["scenario_id"],
            "docs",
            format_delta(row["old_counts"]["all_documents"], row["new_counts"]["all_documents"]),
            "flow",
            format_delta(row["old_counts"]["graph_precedes_edges"], row["new_counts"]["graph_precedes_edges"]),
            "prereq",
            format_delta(row["old_counts"]["prerequisites"], row["new_counts"]["prerequisites"]),
            verdict(row),
        )


if __name__ == "__main__":
    main()
