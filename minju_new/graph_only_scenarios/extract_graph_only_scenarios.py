from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MINJU_ROOT = ROOT.parent
GRAPH_ROOT = MINJU_ROOT / "graph" / "output" / "final_graph"


SCENARIOS = [
    {
        "scenario_id": "mapo_cafe_startup",
        "input": "마포구 카페 창업",
        "district": "마포구",
        "resolution_nodes": ["카페", "휴게음식점영업", "커피전문점 창업", "커피전문점 창업ㆍ운영"],
        "document_subjects": [
            "커피전문점 창업",
            "커피전문점 창업ㆍ운영",
            "휴게음식점영업",
            "식품관련영업신고",
            "영업신고",
            "영업신고 및 사업자등록",
            "사업자등록 신청",
        ],
        "order_terms": [
            "건축물",
            "영업신고",
            "사업자등록",
            "위생교육",
            "건강진단",
            "임대차",
            "안전시설",
            "주류",
            "일반음식점",
        ],
    },
    {
        "scenario_id": "gangnam_restaurant_road_occupation",
        "input": "강남구 일반음식점 + 도로점용",
        "district": "강남구",
        "resolution_nodes": ["일반음식점영업", "외부 공간 사용", "도로ㆍ보도 점용"],
        "document_subjects": [
            "일반음식점영업",
            "식품관련영업신고",
            "영업신고",
            "영업신고 및 사업자등록",
            "사업자등록 신청",
            "도로점용허가",
        ],
        "order_terms": [
            "건축물",
            "영업신고",
            "사업자등록",
            "위생교육",
            "건강진단",
            "임대차",
            "안전시설",
            "도로점용",
            "도로",
            "주류",
            "일반음식점",
        ],
    },
    {
        "scenario_id": "songpa_outdoor_sign",
        "input": "송파구 간판 설치",
        "district": "송파구",
        "resolution_nodes": ["간판 설치", "옥외광고물 등의 표시허가(신고)", "옥외광고물 등의 표시허가"],
        "document_subjects": [
            "옥외광고물 등의 표시허가(신고)",
            "옥외광고물 등의 표시허가",
            "상호 및 광고물",
        ],
        "order_terms": ["간판", "옥외광고", "광고물"],
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def compact(text: str, limit: int = 260) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def edge_payload(edge: dict[str, str]) -> dict[str, str]:
    return {
        "predicate": edge["predicate"],
        "subject_name": edge["subject_name"],
        "object_name": edge["object_name"],
        "subject_type": edge["subject_type"],
        "object_type": edge["object_type"],
        "source_type": edge["source_type"],
        "source_title": edge["title"],
        "section_path": edge["section_path"],
        "source_url": edge["source_url"],
        "chunk_id": edge["chunk_id"],
        "evidence_text": compact(edge["evidence_text"], 360),
        "condition_text": compact(edge["condition_text"], 220),
    }


def unique_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[dict[str, str]] = []
    for edge in edges:
        key = (edge["predicate"], edge["subject_name"], edge["object_name"], edge["chunk_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def related_edges_for_nodes(
    edges: list[dict[str, str]],
    nodes: list[str],
    predicates: set[str],
) -> list[dict[str, str]]:
    node_set = set(nodes)
    return unique_edges(
        [
            edge
            for edge in edges
            if edge["predicate"] in predicates
            and (edge["subject_name"] in node_set or edge["object_name"] in node_set)
        ]
    )


def requires_documents(edges: list[dict[str, str]], subjects: list[str]) -> list[dict[str, str]]:
    subject_set = set(subjects)
    return unique_edges(
        [
            edge
            for edge in edges
            if edge["predicate"] == "requires_document" and edge["subject_name"] in subject_set
        ]
    )


def prerequisites_for(edges: list[dict[str, str]], names: set[str]) -> list[dict[str, str]]:
    return unique_edges(
        [
            edge
            for edge in edges
            if edge["predicate"] == "requires_prerequisite"
            and edge["subject_name"] in names
        ]
    )


def handled_by_for(edges: list[dict[str, str]], names: set[str]) -> list[dict[str, str]]:
    return unique_edges(
        [
            edge
            for edge in edges
            if edge["predicate"] == "handled_by"
            and (edge["subject_name"] in names or edge["object_name"] in names)
        ]
    )


def order_edges_for(edges: list[dict[str, str]], terms: list[str], resolution_edges: list[dict[str, str]]) -> list[dict[str, str]]:
    trigger_edges = [edge for edge in resolution_edges if edge["predicate"] == "triggers"]
    return unique_edges(
        trigger_edges
        +
        [
            edge
            for edge in edges
            if edge["predicate"] == "precedes"
            and any(
                term in " ".join(
                    [
                        edge["subject_name"],
                        edge["object_name"],
                    ]
                )
                for term in terms
            )
        ]
    )


def build_scenario(edges: list[dict[str, str]], scenario: dict[str, object]) -> dict[str, object]:
    resolution_nodes = list(scenario["resolution_nodes"])
    document_subjects = list(scenario["document_subjects"])

    resolution_edges = related_edges_for_nodes(
        edges,
        resolution_nodes,
        {"maps_to", "requires_permit", "triggers", "needs_check", "raises_risk", "based_on"},
    )
    document_edges = requires_documents(edges, document_subjects)
    document_names = {edge["object_name"] for edge in document_edges}
    relevant_names = set(resolution_nodes) | set(document_subjects) | document_names
    prerequisite_edges = prerequisites_for(edges, relevant_names)
    route_edges = handled_by_for(edges, relevant_names)
    order_edges = order_edges_for(edges, list(scenario["order_terms"]), resolution_edges)

    source_edges = related_edges_for_nodes(
        edges,
        sorted(document_names | set(document_subjects)),
        {"has_source", "supported_by", "based_on"},
    )

    return {
        "scenario_id": scenario["scenario_id"],
        "input": scenario["input"],
        "district": scenario["district"],
        "graph_only_note": "지역명은 최종 그래프 노드에 없으므로, 아래 결과의 제출처는 그래프의 department_function까지만 표시한다.",
        "resolved_graph_edges": [edge_payload(edge) for edge in resolution_edges],
        "required_documents": [edge_payload(edge) for edge in document_edges],
        "document_prerequisites": [edge_payload(edge) for edge in prerequisite_edges],
        "submission_routes": [edge_payload(edge) for edge in route_edges],
        "order_and_trigger_edges": [edge_payload(edge) for edge in order_edges],
        "source_and_legal_edges": [edge_payload(edge) for edge in source_edges[:120]],
    }


def write_markdown(results: list[dict[str, object]], path: Path) -> None:
    lines: list[str] = [
        "# Graph Only Scenario Results",
        "",
        "최종 그래프 CSV에서 직접 추출한 결과입니다. `document_issue_guide`의 보강 라벨이나 rule-based 발급처 라벨은 사용하지 않았습니다.",
        "지역명은 최종 그래프에 없으므로 실제 자치구 과명은 이 파일에 포함하지 않았습니다.",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result['input']}",
                "",
                f"- district_in_input: {result['district']}",
                f"- graph_only_note: {result['graph_only_note']}",
                "",
                "### 입력이 그래프에서 해석된 경로",
            ]
        )
        for edge in result["resolved_graph_edges"]:
            lines.append(
                f"- `{edge['predicate']}` {edge['subject_name']} -> {edge['object_name']} ({edge['source_title']})"
            )

        lines.extend(["", "### 필요한 서류"])
        for edge in result["required_documents"]:
            suffix = f" / 조건: {edge['condition_text']}" if edge["condition_text"] else ""
            lines.append(
                f"- {edge['object_name']} <- {edge['subject_name']} [{edge['source_title']} / {edge['section_path']}]{suffix}"
            )

        lines.extend(["", "### 선행요건"])
        if result["document_prerequisites"]:
            for edge in result["document_prerequisites"]:
                lines.append(f"- {edge['subject_name']} 전에 {edge['object_name']} (`requires_prerequisite`)")
        else:
            lines.append("- 그래프에 직접 연결된 `requires_prerequisite` 없음")

        lines.extend(["", "### 제출/문의 기능"])
        if result["submission_routes"]:
            for edge in result["submission_routes"]:
                lines.append(f"- {edge['subject_name']} -> {edge['object_name']} (`handled_by`)")
        else:
            lines.append("- 그래프에 직접 연결된 `handled_by` 없음")

        lines.extend(["", "### 순서/트리거"])
        if result["order_and_trigger_edges"]:
            for edge in result["order_and_trigger_edges"]:
                lines.append(f"- `{edge['predicate']}` {edge['subject_name']} -> {edge['object_name']} ({edge['source_title']})")
        else:
            lines.append("- 그래프에 직접 연결된 `precedes`/`triggers` 없음")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    edges = read_csv(GRAPH_ROOT / "graph_edges_high_precision.csv")
    results = [build_scenario(edges, scenario) for scenario in SCENARIOS]
    (ROOT / "scenario_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(results, ROOT / "scenario_results.md")
    summary = {
        "scenario_count": len(results),
        "source_graph_edges": str(GRAPH_ROOT / "graph_edges_high_precision.csv"),
        "outputs": ["scenario_results.json", "scenario_results.md"],
        "counts": {
            result["scenario_id"]: {
                "resolved_graph_edges": len(result["resolved_graph_edges"]),
                "required_documents": len(result["required_documents"]),
                "document_prerequisites": len(result["document_prerequisites"]),
                "submission_routes": len(result["submission_routes"]),
                "order_and_trigger_edges": len(result["order_and_trigger_edges"]),
            }
            for result in results
        },
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
