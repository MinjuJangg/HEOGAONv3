from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from build_graph_from_claims import (
    EDGE_COLUMNS,
    NODE_COLUMNS,
    build_graph,
    enrich_seed_validation,
    parse_seed_claims,
    write_csv,
)


GRAPH_ROOT = Path(__file__).resolve().parents[1]
INPUT = GRAPH_ROOT / "input"
OUT = GRAPH_ROOT / "output" / "final_graph"
SEEDS = GRAPH_ROOT / "seeds"

DEFAULT_BASE_NODES = INPUT / "base_graph" / "graph_nodes_high_precision.csv"
DEFAULT_BASE_EDGES = INPUT / "base_graph" / "graph_edges_high_precision.csv"
DEFAULT_EVIDENCE = INPUT / "evidence" / "evidence_chunks_augmented.jsonl"
DEFAULT_OUT_NODES = OUT / "graph_nodes_high_precision.csv"
DEFAULT_OUT_EDGES = OUT / "graph_edges_high_precision.csv"
DEFAULT_MANIFEST = OUT / "final_graph_manifest.md"
DEFAULT_PROVENANCE_REPORT = OUT / "seed_evidence_provenance_report.md"
DEFAULT_SEED_FILES = [
    SEEDS / "core_route_seed.yaml",
    SEEDS / "core_document_check_seed.yaml",
    SEEDS / "core_department_seed.yaml",
    SEEDS / "core_procedure_seed.yaml",
    SEEDS / "core_before_prerequisite_seed.yaml",
]

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣·]+")
STOPWORDS = {
    "또는",
    "그리고",
    "그",
    "해당",
    "여부",
    "확인",
    "필요",
    "대상",
    "신청",
    "신고",
    "허가",
    "증명서",
    "수료증",
    "계약서",
    "신분증",
    "완료",
    "준비",
    "발급",
}


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def int_value(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def merge_nodes(base_rows: list[dict[str, Any]], seed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in base_rows:
        node_key = row.get("node_id", "")
        if node_key:
            merged[node_key] = {column: row.get(column, "") for column in NODE_COLUMNS}

    for row in seed_rows:
        node_key = row.get("node_id", "")
        if not node_key:
            continue
        incoming = {column: row.get(column, "") for column in NODE_COLUMNS}
        if node_key not in merged:
            merged[node_key] = incoming
            continue
        existing = merged[node_key]
        for column in NODE_COLUMNS:
            if column == "claim_count":
                continue
            if not existing.get(column) and incoming.get(column):
                existing[column] = incoming[column]
        existing["claim_count"] = str(int_value(existing.get("claim_count")) + int_value(incoming.get("claim_count")))

    return sorted(merged.values(), key=lambda row: (row.get("node_type", ""), row.get("name", ""), row.get("node_id", "")))


def merge_edges(base_rows: list[dict[str, Any]], seed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    seen_relation_keys: set[tuple[str, str, str, str, str]] = set()

    for row in base_rows:
        edge_key = row.get("edge_id", "")
        if not edge_key:
            continue
        clean = {column: row.get(column, "") for column in EDGE_COLUMNS}
        merged[edge_key] = clean
        seen_relation_keys.add(relation_key(clean))

    for row in seed_rows:
        edge_key = row.get("edge_id", "")
        if not edge_key:
            continue
        clean = {column: row.get(column, "") for column in EDGE_COLUMNS}
        rel_key = relation_key(clean)
        if edge_key in merged or rel_key in seen_relation_keys:
            continue
        merged[edge_key] = clean
        seen_relation_keys.add(rel_key)

    return sorted(merged.values(), key=lambda row: (row.get("predicate", ""), row.get("source_node_id", ""), row.get("target_node_id", "")))


def relation_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        row.get("subject_type", ""),
        row.get("subject_name", ""),
        row.get("predicate", ""),
        row.get("object_type", ""),
        row.get("object_name", ""),
    )


def tokens(value: Any) -> list[str]:
    output = []
    seen = set()
    for token in TOKEN_RE.findall(str(value or "")):
        token = token.strip().casefold()
        if len(token) < 2 or token in STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            output.append(token)
    return output


def claim_terms(claim: dict[str, Any]) -> list[str]:
    terms = []
    for key in ["subject_name", "object_name"]:
        value = claim.get(key, "")
        if value:
            terms.append(str(value))
    terms.extend(tokens(" ".join(str(claim.get(key, "")) for key in ["subject_name", "object_name", "condition_text"])))
    seen = set()
    output = []
    for term in terms:
        key = term.casefold()
        if key and key not in seen:
            seen.add(key)
            output.append(term)
    return output


def evidence_haystack(evidence: dict[str, Any]) -> str:
    return " ".join(
        str(evidence.get(key, ""))
        for key in ["title", "section_path", "text", "source_document_id", "source_type"]
    ).casefold()


def evidence_score(claim: dict[str, Any], evidence: dict[str, Any]) -> int:
    haystack = evidence_haystack(evidence)
    subject = str(claim.get("subject_name", "")).casefold()
    obj = str(claim.get("object_name", "")).casefold()
    score = 0
    if subject and subject in haystack:
        score += 8
    if obj and obj in haystack:
        score += 8
    for term in claim_terms(claim):
        needle = term.casefold()
        if len(needle) >= 2 and needle in haystack:
            score += 2 if len(needle) > 5 else 1
    predicate = claim.get("predicate", "")
    if predicate == "requires_document" and evidence.get("source_type") == "gov24":
        score += 2
    if predicate in {"based_on", "raises_risk"} and "law_" in str(evidence.get("source_document_id", "")):
        score += 2
    if "커피전문점" in haystack or "음식점 창업" in haystack or "식품관련영업신고" in haystack:
        score += 1
    return score


def attach_evidence(
    claims: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    *,
    min_score: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    provenance: list[dict[str, Any]] = []
    for claim in claims:
        scored = sorted(
            (
                (evidence_score(claim, evidence), evidence)
                for evidence in evidence_rows
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best = scored[0] if scored else (0, {})
        relation = {
            "subject": claim.get("subject_name", ""),
            "predicate": claim.get("predicate", ""),
            "object": claim.get("object_name", ""),
            "seed_file": claim.get("seed_file", ""),
            "best_score": best_score,
            "chunk_id": best.get("chunk_id", ""),
            "source_document_id": best.get("source_document_id", ""),
            "title": best.get("title", ""),
            "source_url": best.get("source_url", ""),
            "raw_path": best.get("raw_path", ""),
        }
        if best_score >= min_score:
            claim["source_document_id"] = best.get("source_document_id", "")
            claim["chunk_id"] = best.get("chunk_id", "")
            claim["source_type"] = best.get("source_type", "")
            claim["source_url"] = best.get("source_url", "")
            claim["title"] = best.get("title", "")
            claim["section_path"] = best.get("section_path", "")
            claim["evidence_text"] = str(best.get("text", ""))[:800]
            claim["extraction_method"] = "source_backed_seed"
            claim["review_status"] = "source_backed_curated"
            relation["status"] = "source_backed"
        else:
            relation["status"] = "curated_unmatched"
        provenance.append(relation)
    return claims, provenance


def load_seed_claims(seed_paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for seed_path in seed_paths:
        for claim in parse_seed_claims(seed_path):
            claim = enrich_seed_validation(claim)
            claim["seed_file"] = str(seed_path)
            if claim.get("validation_errors"):
                invalid.append(claim)
            else:
                valid.append(claim)
    return valid, invalid


def stats(rows: list[dict[str, Any]], key: str) -> Counter[str]:
    return Counter(row.get(key, "") for row in rows if row.get(key, ""))


def counter_lines(counter: Counter[str]) -> str:
    if not counter:
        return "- (none)"
    return "\n".join(f"- {key}: {value}" for key, value in counter.most_common())


def provenance_report_text(provenance: list[dict[str, Any]]) -> str:
    counts = Counter(row.get("status", "") for row in provenance)
    source_counts = Counter(row.get("source_document_id", "") for row in provenance if row.get("status") == "source_backed")

    def relation_line(row: dict[str, Any]) -> str:
        return (
            f"- {row.get('subject')} --{row.get('predicate')}--> {row.get('object')} "
            f"| score={row.get('best_score')} | source={row.get('source_document_id') or '(none)'} "
            f"| chunk={row.get('chunk_id') or '(none)'}"
        )

    unmatched = [row for row in provenance if row.get("status") != "source_backed"]
    matched = [row for row in provenance if row.get("status") == "source_backed"]
    return f"""# Seed Evidence Provenance Report

## Summary

- total_seed_claims: {len(provenance)}
- source_backed: {counts.get("source_backed", 0)}
- curated_unmatched: {counts.get("curated_unmatched", 0)}

## Source Documents Used

{counter_lines(source_counts)}

## Curated Claims Without Strong Evidence Match

{chr(10).join(relation_line(row) for row in unmatched) if unmatched else "- 없음"}

## Source-Backed Claims

{chr(10).join(relation_line(row) for row in matched)}
"""


def manifest_text(
    *,
    args: argparse.Namespace,
    seed_claims: list[dict[str, Any]],
    invalid_seed_claims: list[dict[str, Any]],
    base_nodes: list[dict[str, Any]],
    base_edges: list[dict[str, Any]],
    seed_nodes: list[dict[str, Any]],
    seed_edges: list[dict[str, Any]],
    final_nodes: list[dict[str, Any]],
    final_edges: list[dict[str, Any]],
) -> str:
    return f"""# Final Service Graph Manifest

## Build Inputs

- base_nodes: {args.base_nodes}
- base_edges: {args.base_edges}
- evidence: {args.evidence}
- attach_evidence: {args.attach_evidence}
- evidence_min_score: {args.evidence_min_score}
- require_evidence_for_seeds: {args.require_evidence_for_seeds}
- seed_files:
{chr(10).join(f"  - {path}" for path in args.seed)}

## Build Method

1. Load the existing high precision graph CSV files.
2. Parse service seed claims as candidate relations for route, document, check, department function, and procedure order.
3. Attach the best matching official/raw evidence chunk to each seed claim when the evidence score is strong enough.
4. When require_evidence_for_seeds is true, discard seed claims that do not receive an evidence match.
5. Validate every remaining seed claim against the ontology predicate/type rules.
6. Build seed nodes and edges with the same stable node id logic as the original graph builder.
7. Merge seed graph into the existing graph and de-duplicate by edge id plus relation tuple.

## Counts

- base_nodes: {len(base_nodes)}
- base_edges: {len(base_edges)}
- valid_seed_claims: {len(seed_claims)}
- invalid_seed_claims: {len(invalid_seed_claims)}
- seed_nodes: {len(seed_nodes)}
- seed_edges: {len(seed_edges)}
- final_nodes: {len(final_nodes)}
- final_edges: {len(final_edges)}
- added_nodes: {len(final_nodes) - len(base_nodes)}
- added_edges: {len(final_edges) - len(base_edges)}

## Final Node Types

{counter_lines(stats(final_nodes, "node_type"))}

## Final Edge Predicates

{counter_lines(stats(final_edges, "predicate"))}

## Final Edge Sources

{counter_lines(stats(final_edges, "edge_source"))}

## Notes

- Regional real department names are intentionally not hard-coded in this graph. The graph stores reusable department functions such as 식품위생 업무 and 옥외광고물 관리 업무.
- Local department name mapping should be applied as a separate lookup layer when a district is selected.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge final service seed claims into the existing high precision graph.")
    parser.add_argument("--base-nodes", type=Path, default=DEFAULT_BASE_NODES)
    parser.add_argument("--base-edges", type=Path, default=DEFAULT_BASE_EDGES)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--seed", type=Path, action="append", default=DEFAULT_SEED_FILES)
    parser.add_argument("--out-nodes", type=Path, default=DEFAULT_OUT_NODES)
    parser.add_argument("--out-edges", type=Path, default=DEFAULT_OUT_EDGES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--provenance-report", type=Path, default=DEFAULT_PROVENANCE_REPORT)
    parser.add_argument("--attach-evidence", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--evidence-min-score", type=int, default=6)
    parser.add_argument("--require-evidence-for-seeds", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_nodes = read_csv(args.base_nodes)
    base_edges = read_csv(args.base_edges)
    seed_claims, invalid_seed_claims = load_seed_claims(args.seed)
    provenance: list[dict[str, Any]] = []
    if args.attach_evidence:
        seed_claims, provenance = attach_evidence(
            seed_claims,
            read_jsonl(args.evidence),
            min_score=args.evidence_min_score,
        )
        if args.require_evidence_for_seeds:
            seed_claims = [
                claim
                for claim in seed_claims
                if claim.get("extraction_method") == "source_backed_seed"
            ]
    if invalid_seed_claims:
        print(f"invalid_seed_claims={len(invalid_seed_claims)}")
        for claim in invalid_seed_claims[:20]:
            print(
                f"- {claim.get('seed_file')}: {claim.get('subject_type')} "
                f"{claim.get('predicate')} {claim.get('object_type')} "
                f"{claim.get('validation_errors')}"
            )
        raise SystemExit(1)

    seed_nodes, seed_edges, _rag_rows, _seed_stats = build_graph(
        seed_claims,
        {},
        include_grounding_edges=False,
    )
    final_nodes = merge_nodes(base_nodes, seed_nodes)
    final_edges = merge_edges(base_edges, seed_edges)

    write_csv(args.out_nodes, final_nodes, NODE_COLUMNS)
    write_csv(args.out_edges, final_edges, EDGE_COLUMNS)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        manifest_text(
            args=args,
            seed_claims=seed_claims,
            invalid_seed_claims=invalid_seed_claims,
            base_nodes=base_nodes,
            base_edges=base_edges,
            seed_nodes=seed_nodes,
            seed_edges=seed_edges,
            final_nodes=final_nodes,
            final_edges=final_edges,
        ),
        encoding="utf-8",
    )
    if provenance:
        args.provenance_report.parent.mkdir(parents=True, exist_ok=True)
        args.provenance_report.write_text(provenance_report_text(provenance), encoding="utf-8")

    print(
        f"base_nodes={len(base_nodes)} base_edges={len(base_edges)} "
        f"seed_claims={len(seed_claims)} final_nodes={len(final_nodes)} final_edges={len(final_edges)}"
    )
    print(f"out_nodes={args.out_nodes}")
    print(f"out_edges={args.out_edges}")
    print(f"manifest={args.manifest}")
    if provenance:
        print(f"provenance_report={args.provenance_report}")


if __name__ == "__main__":
    main()
