from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from run_llm_claim_extraction import ALLOWED_PAIRS, OUT, clean_text, iter_jsonl


GRAPH_ROOT = Path(__file__).resolve().parents[1]
BASE_OUT = GRAPH_ROOT / "output" / "base_graph"

DEFAULT_CLAIMS = OUT / "llm_claims_final.jsonl"
DEFAULT_EVIDENCE = OUT / "evidence_chunks.jsonl"
DEFAULT_ONTOLOGY = Path(__file__).resolve().parents[1] / "ontology" / "cafe_restaurant_mvp.yaml"
DEFAULT_NODES = BASE_OUT / "graph_nodes_high_precision.csv"
DEFAULT_EDGES = BASE_OUT / "graph_edges_high_precision.csv"
DEFAULT_RAG_EVIDENCE = BASE_OUT / "rag_evidence_chunks_high_precision.jsonl"
DEFAULT_MANIFEST = BASE_OUT / "graph_build_manifest_high_precision.md"


NODE_COLUMNS = [
    "node_id",
    "node_type",
    "name",
    "normalized_name",
    "source_document_id",
    "chunk_id",
    "source_type",
    "source_url",
    "title",
    "section_path",
    "claim_count",
]

EDGE_COLUMNS = [
    "edge_id",
    "source_node_id",
    "target_node_id",
    "predicate",
    "subject_type",
    "subject_name",
    "object_type",
    "object_name",
    "claim_id",
    "edge_source",
    "assertion_level",
    "authority_level",
    "review_status",
    "confidence",
    "source_document_id",
    "chunk_id",
    "evidence_text",
    "condition_text",
    "source_type",
    "source_url",
    "title",
    "section_path",
    "extraction_method",
    "model",
]


HAS_SOURCE_TYPES = {
    object_type
    for subject_type, object_type in ALLOWED_PAIRS.get("has_source", set())
    if object_type == "source_document"
}
HAS_SOURCE_SUBJECT_TYPES = {
    subject_type for subject_type, object_type in ALLOWED_PAIRS.get("has_source", set())
    if object_type == "source_document"
}


def stable_hash(*parts: Any, length: int = 16) -> str:
    payload = "\u241f".join(str(part or "") for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]


def node_id(node_type: str, name: str) -> str:
    return f"n_{stable_hash(node_type, normalize_name(name))}"


def source_document_node_id(source_document_id: str) -> str:
    return f"src_{stable_hash(source_document_id)}"


def evidence_node_id(chunk_id: str) -> str:
    return f"ev_{stable_hash(chunk_id)}"


def normalize_name(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_seed_claims(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_seed_claims = False
    claims: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in lines:
        if raw_line.startswith("seed_claims:"):
            in_seed_claims = True
            continue
        if in_seed_claims and raw_line and not raw_line.startswith(" "):
            break
        if not in_seed_claims:
            continue

        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current:
                claims.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if ":" not in stripped or current is None:
            continue
        key, value = stripped.split(":", 1)
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if key == "confidence":
            try:
                current[key] = float(value)
            except ValueError:
                current[key] = value
        else:
            current[key] = value

    if current:
        claims.append(current)

    normalized: list[dict[str, Any]] = []
    for claim in claims:
        if not all(
            claim.get(field)
            for field in ["subject_type", "subject_name", "predicate", "object_type", "object_name"]
        ):
            continue
        seed = {
            **claim,
            "claim_id": f"seed_{stable_hash(claim.get('subject_type'), claim.get('subject_name'), claim.get('predicate'), claim.get('object_type'), claim.get('object_name'))}",
            "source_document_id": claim.get("source_document_id") or f"{path.stem}_seed",
            "chunk_id": claim.get("chunk_id", ""),
            "source_type": claim.get("source_type") or "curated_seed",
            "source_url": claim.get("source_url", ""),
            "title": claim.get("title") or f"{path.stem} seed",
            "section_path": claim.get("section_path") or "seed_claims",
            "evidence_text": claim.get("condition_text", ""),
            "extraction_method": claim.get("extraction_method") or "rule_seed",
            "model": "",
            "validation_errors": [],
        }
        normalized.append(seed)
    return normalized


def confidence_value(claim: dict[str, Any]) -> float:
    try:
        return float(claim.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_review_status(claim: dict[str, Any]) -> str:
    status = normalize_name(claim.get("review_status", ""))
    if status in {"official_document", "source_backed_curated", "rule_seed", "llm_inferred", "needs_review", "rejected"}:
        return status
    if status.startswith("official_"):
        return "official_document"
    if claim.get("extraction_method") == "rule_seed" or claim.get("authority_level") == "rule_seed":
        return "rule_seed"
    return "llm_inferred" if status else ""


def enrich_seed_validation(claim: dict[str, Any]) -> dict[str, Any]:
    predicate = claim.get("predicate", "")
    pair = (claim.get("subject_type", ""), claim.get("object_type", ""))
    errors = []
    if predicate not in ALLOWED_PAIRS:
        errors.append("invalid_predicate")
    elif pair not in ALLOWED_PAIRS[predicate]:
        errors.append("invalid_type_pair")
    claim["validation_errors"] = errors
    return claim


def add_node(
    nodes: dict[str, dict[str, Any]],
    node_type: str,
    name: str,
    *,
    source_document_id: str = "",
    chunk_id: str = "",
    source_type: str = "",
    source_url: str = "",
    title: str = "",
    section_path: str = "",
) -> str:
    clean_name = normalize_name(name)
    if node_type == "source_document":
        node_key = source_document_node_id(clean_name)
    elif node_type == "evidence_chunk":
        node_key = evidence_node_id(clean_name)
    else:
        node_key = node_id(node_type, clean_name)

    node = nodes.setdefault(
        node_key,
        {
            "node_id": node_key,
            "node_type": node_type,
            "name": clean_name,
            "normalized_name": normalize_name(clean_name).casefold(),
            "source_document_id": "",
            "chunk_id": "",
            "source_type": "",
            "source_url": "",
            "title": "",
            "section_path": "",
            "claim_count": 0,
        },
    )
    for key, value in {
        "source_document_id": source_document_id,
        "chunk_id": chunk_id,
        "source_type": source_type,
        "source_url": source_url,
        "title": title,
        "section_path": section_path,
    }.items():
        if value and not node.get(key):
            node[key] = value
    return node_key


def add_edge(edges: dict[str, dict[str, Any]], edge: dict[str, Any]) -> None:
    edges[edge["edge_id"]] = edge


def load_evidence(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row.get("chunk_id", ""): row for row in iter_jsonl(path) if row.get("chunk_id")}


def build_graph(
    claims: list[dict[str, Any]],
    evidence_by_chunk: dict[str, dict[str, Any]],
    *,
    include_grounding_edges: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    node_claim_counts: Counter[str] = Counter()
    referenced_chunks: set[str] = set()
    chunk_claims: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for claim in claims:
        if claim.get("validation_errors"):
            continue

        subject_type = normalize_name(claim.get("subject_type", ""))
        object_type = normalize_name(claim.get("object_type", ""))
        subject_name = normalize_name(claim.get("subject_name", ""))
        object_name = normalize_name(claim.get("object_name", ""))
        predicate = normalize_name(claim.get("predicate", ""))
        if not all([subject_type, object_type, subject_name, object_name, predicate]):
            continue

        source_document_id = normalize_name(claim.get("source_document_id", ""))
        chunk_id = normalize_name(claim.get("chunk_id", ""))
        evidence = evidence_by_chunk.get(chunk_id, {})
        source_type = claim.get("source_type") or evidence.get("source_type", "")
        source_url = claim.get("source_url") or evidence.get("source_url", "")
        title = claim.get("title") or evidence.get("title", "")
        section_path = claim.get("section_path") or evidence.get("section_path", "")

        subject_id = add_node(
            nodes,
            subject_type,
            subject_name,
            source_document_id=source_document_id,
            chunk_id=chunk_id,
            source_type=source_type,
            source_url=source_url,
            title=title,
            section_path=section_path,
        )
        object_id = add_node(
            nodes,
            object_type,
            object_name,
            source_document_id=source_document_id,
            chunk_id=chunk_id,
            source_type=source_type,
            source_url=source_url,
            title=title,
            section_path=section_path,
        )
        node_claim_counts[subject_id] += 1
        node_claim_counts[object_id] += 1

        claim_id = normalize_name(claim.get("claim_id")) or f"claim_{stable_hash(subject_id, predicate, object_id, chunk_id)}"
        review_status = normalize_review_status(claim)
        if claim.get("extraction_method") == "source_backed_seed":
            edge_source = "source_backed_seed"
        elif review_status == "rule_seed":
            edge_source = "rule_seed"
        elif claim.get("extraction_method") == "gov24_html_list_parser":
            edge_source = "gov24_parser"
        else:
            edge_source = "llm_claim"
        add_edge(
            edges,
            {
                "edge_id": f"edge_{stable_hash('claim', claim_id)}",
                "source_node_id": subject_id,
                "target_node_id": object_id,
                "predicate": predicate,
                "subject_type": subject_type,
                "subject_name": subject_name,
                "object_type": object_type,
                "object_name": object_name,
                "claim_id": claim_id,
                "edge_source": edge_source,
                "assertion_level": claim.get("assertion_level", ""),
                "authority_level": claim.get("authority_level", ""),
                "review_status": review_status,
                "confidence": claim.get("confidence", ""),
                "source_document_id": source_document_id,
                "chunk_id": chunk_id,
                "evidence_text": claim.get("evidence_text", ""),
                "condition_text": claim.get("condition_text", ""),
                "source_type": source_type,
                "source_url": source_url,
                "title": title,
                "section_path": section_path,
                "extraction_method": claim.get("extraction_method", ""),
                "model": claim.get("model", ""),
            },
        )

        if chunk_id:
            referenced_chunks.add(chunk_id)
            chunk_claims[chunk_id].append(claim)

        if not include_grounding_edges or not source_document_id:
            continue

        source_doc_id = add_node(
            nodes,
            "source_document",
            source_document_id,
            source_document_id=source_document_id,
            source_type=source_type,
            source_url=source_url,
            title=title,
        )
        for n_type, n_id in [(subject_type, subject_id), (object_type, object_id)]:
            if n_type not in HAS_SOURCE_SUBJECT_TYPES:
                continue
            add_edge(
                edges,
                {
                    "edge_id": f"edge_{stable_hash('has_source', n_id, source_doc_id)}",
                    "source_node_id": n_id,
                    "target_node_id": source_doc_id,
                    "predicate": "has_source",
                    "subject_type": n_type,
                    "subject_name": nodes[n_id]["name"],
                    "object_type": "source_document",
                    "object_name": source_document_id,
                    "claim_id": "",
                    "edge_source": "derived_grounding",
                    "assertion_level": "explicit",
                    "authority_level": claim.get("authority_level", ""),
                    "review_status": review_status,
                    "confidence": claim.get("confidence", ""),
                    "source_document_id": source_document_id,
                    "chunk_id": chunk_id,
                    "evidence_text": "",
                    "condition_text": "",
                    "source_type": source_type,
                    "source_url": source_url,
                    "title": title,
                    "section_path": section_path,
                    "extraction_method": "derived",
                    "model": "",
                },
            )

        if chunk_id:
            evidence_title = evidence.get("section_path") or evidence.get("title") or chunk_id
            ev_node_id = add_node(
                nodes,
                "evidence_chunk",
                chunk_id,
                source_document_id=source_document_id,
                chunk_id=chunk_id,
                source_type=source_type,
                source_url=source_url,
                title=evidence_title,
                section_path=evidence.get("section_path", ""),
            )
            add_edge(
                edges,
                {
                    "edge_id": f"edge_{stable_hash('supported_by', source_doc_id, ev_node_id)}",
                    "source_node_id": source_doc_id,
                    "target_node_id": ev_node_id,
                    "predicate": "supported_by",
                    "subject_type": "source_document",
                    "subject_name": source_document_id,
                    "object_type": "evidence_chunk",
                    "object_name": chunk_id,
                    "claim_id": "",
                    "edge_source": "derived_grounding",
                    "assertion_level": "explicit",
                    "authority_level": claim.get("authority_level", ""),
                    "review_status": review_status,
                    "confidence": claim.get("confidence", ""),
                    "source_document_id": source_document_id,
                    "chunk_id": chunk_id,
                    "evidence_text": "",
                    "condition_text": "",
                    "source_type": source_type,
                    "source_url": source_url,
                    "title": title,
                    "section_path": section_path,
                    "extraction_method": "derived",
                    "model": "",
                },
            )

    for node_key, count in node_claim_counts.items():
        nodes[node_key]["claim_count"] = count

    rag_rows: list[dict[str, Any]] = []
    for chunk_id in sorted(referenced_chunks):
        evidence = evidence_by_chunk.get(chunk_id)
        if not evidence:
            continue
        claims_for_chunk = chunk_claims.get(chunk_id, [])
        rag_rows.append(
            {
                **evidence,
                "referenced_claim_count": len(claims_for_chunk),
                "referenced_predicates": sorted({claim.get("predicate", "") for claim in claims_for_chunk}),
                "referenced_node_names": sorted(
                    {
                        normalize_name(claim.get(name_key, ""))
                        for claim in claims_for_chunk
                        for name_key in ["subject_name", "object_name"]
                        if claim.get(name_key)
                    }
                ),
            }
        )

    node_rows = sorted(nodes.values(), key=lambda row: (row["node_type"], row["name"], row["node_id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (row["predicate"], row["source_node_id"], row["target_node_id"]))
    stats = {
        "nodes": len(node_rows),
        "edges": len(edge_rows),
        "rag_evidence_chunks": len(rag_rows),
        "node_types": Counter(row["node_type"] for row in node_rows),
        "edge_predicates": Counter(row["predicate"] for row in edge_rows),
        "edge_sources": Counter(row["edge_source"] for row in edge_rows),
    }
    return node_rows, edge_rows, rag_rows, stats


def manifest_text(stats: dict[str, Any], args: argparse.Namespace, claims_count: int) -> str:
    def counter_lines(counter: Counter[str]) -> str:
        return "\n".join(f"- {key}: {value}" for key, value in counter.most_common())

    return f"""# Graph Build Manifest

## Inputs

- claims: {args.claims}
- evidence: {args.evidence}
- ontology: {args.ontology}
- extra_seeds: {", ".join(str(path) for path in getattr(args, "extra_seed", []) or []) or "(none)"}
- input_claims: {claims_count}
- min_confidence: {args.min_confidence}
- include_rule_seeds: {args.include_rule_seeds}
- include_grounding_edges: {args.include_grounding_edges}

## Outputs

- graph_nodes: {args.nodes}
- graph_edges: {args.edges}
- rag_evidence_chunks: {args.rag_evidence}

## Counts

- nodes: {stats["nodes"]}
- edges: {stats["edges"]}
- rag_evidence_chunks: {stats["rag_evidence_chunks"]}

## Node Types

{counter_lines(stats["node_types"])}

## Edge Predicates

{counter_lines(stats["edge_predicates"])}

## Edge Sources

{counter_lines(stats["edge_sources"])}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GraphRAG node/edge CSV files from validated claims.")
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--rag-evidence", type=Path, default=DEFAULT_RAG_EVIDENCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--extra-seed", type=Path, action="append", default=[])
    parser.add_argument("--include-rule-seeds", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-grounding-edges", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    claims = [
        claim
        for claim in iter_jsonl(args.claims)
        if not claim.get("validation_errors") and confidence_value(claim) >= args.min_confidence
    ]
    if args.include_rule_seeds:
        for seed_path in [args.ontology, *args.extra_seed]:
            claims.extend(enrich_seed_validation(claim) for claim in parse_seed_claims(seed_path))

    evidence_by_chunk = load_evidence(args.evidence)
    nodes, edges, rag_rows, stats = build_graph(
        claims,
        evidence_by_chunk,
        include_grounding_edges=args.include_grounding_edges,
    )

    write_csv(args.nodes, nodes, NODE_COLUMNS)
    write_csv(args.edges, edges, EDGE_COLUMNS)
    write_jsonl(args.rag_evidence, rag_rows)
    args.manifest.write_text(manifest_text(stats, args, len(claims)), encoding="utf-8")

    print(f"claims={len(claims)} nodes={len(nodes)} edges={len(edges)} rag_evidence_chunks={len(rag_rows)}")
    print(f"nodes={args.nodes}")
    print(f"edges={args.edges}")
    print(f"rag_evidence={args.rag_evidence}")
    print(f"manifest={args.manifest}")


if __name__ == "__main__":
    main()
