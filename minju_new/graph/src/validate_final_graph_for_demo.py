from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


GRAPH_ROOT = Path(__file__).resolve().parents[1]
OUT = GRAPH_ROOT / "output" / "final_graph"
DEFAULT_NODES = OUT / "graph_nodes_high_precision.csv"
DEFAULT_EDGES = OUT / "graph_edges_high_precision.csv"
DEFAULT_REPORT = OUT / "final_graph_validation_report.md"

MIN_PREDICATES = {
    "requires_document": 600,
    "needs_check": 200,
    "requires_prerequisite": 20,
    "precedes": 15,
    "handled_by": 10,
    "triggers": 130,
    "requires_permit": 8,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_report(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    nodes = read_csv(args.nodes)
    edges = read_csv(args.edges)
    predicate_counts = Counter(edge["predicate"] for edge in edges)
    edge_source_counts = Counter(edge["edge_source"] for edge in edges)
    node_type_counts = Counter(node["node_type"] for node in nodes)

    errors: list[str] = []

    for predicate, minimum in MIN_PREDICATES.items():
        actual = predicate_counts.get(predicate, 0)
        if actual < minimum:
            errors.append(f"{predicate}: actual {actual}, expected at least {minimum}")

    detail_seed_edges = [
        edge for edge in edges
        if edge.get("authority_level") == "detail_prerequisite_seed"
    ]
    if detail_seed_edges:
        errors.append(f"detail_prerequisite_seed edges remain: {len(detail_seed_edges)}")

    bad_source_backed = [
        edge for edge in edges
        if edge.get("edge_source") == "source_backed_seed"
        and (not edge.get("chunk_id") or not edge.get("source_document_id"))
    ]
    if bad_source_backed:
        errors.append(f"source_backed_seed edges without evidence metadata: {len(bad_source_backed)}")

    if edge_source_counts.get("source_backed_seed", 0) == 0:
        errors.append("no source_backed_seed edges")
    if edge_source_counts.get("llm_claim", 0) == 0:
        errors.append("no llm_claim edges")
    if edge_source_counts.get("gov24_parser", 0) == 0:
        errors.append("no gov24_parser edges")

    status = "FAIL" if errors else "PASS"
    lines = [
        "# Final Graph Validation Report",
        "",
        "## Result",
        "",
        f"- status: {status}",
        f"- nodes: {len(nodes)}",
        f"- edges: {len(edges)}",
        "",
        "## Data Grounding Checks",
        "",
        f"- detail_prerequisite_seed_edges: {len(detail_seed_edges)}",
        f"- source_backed_seed_without_evidence_metadata: {len(bad_source_backed)}",
        f"- source_backed_seed_edges: {edge_source_counts.get('source_backed_seed', 0)}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {error}" for error in errors)
    if not errors:
        lines.append("- 없음")
    lines.extend(["", "## Edge Predicate Counts", ""])
    lines.extend(f"- {name}: {count}" for name, count in predicate_counts.most_common())
    lines.extend(["", "## Edge Source Counts", ""])
    lines.extend(f"- {name}: {count}" for name, count in edge_source_counts.most_common())
    lines.extend(["", "## Node Type Counts", ""])
    lines.extend(f"- {name}: {count}" for name, count in node_type_counts.most_common())
    write_report(args.report, lines)
    print("\n".join(lines))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
