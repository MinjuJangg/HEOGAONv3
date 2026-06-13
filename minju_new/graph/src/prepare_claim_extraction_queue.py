from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


GRAPH_ROOT = Path(__file__).resolve().parents[1]
OUT = GRAPH_ROOT / "output" / "intermediate"
DEFAULT_EVIDENCE = OUT / "evidence_chunks.jsonl"
DEFAULT_QUEUE = OUT / "claim_extraction_queue.jsonl"
DEFAULT_MANIFEST = OUT / "claim_extraction_queue_manifest.md"

DEFAULT_TARGET_TAGS = {
    "food_business",
    "hygiene",
    "building",
    "business_registration",
    "signage",
    "road",
    "liquor",
    "safety",
}

CAFE_RESTAURANT_EASYLAW_RECORDS = {"706", "839", "840"}
CAFE_RESTAURANT_GOV24_RECORDS = {
    "food_business_report",
    "outdoor_ad_permit_report",
    "road_occupation_permit",
    "ecommerce_report",
}
CAFE_RESTAURANT_LAW_BUCKETS = {
    "식품위생법": "food",
    "식품위생법 시행령": "food",
    "식품위생법 시행규칙": "food",
    "주류 면허 등에 관한 법률": "liquor",
    "주류 면허 등에 관한 법률 시행령": "liquor",
    "주류 면허 등에 관한 법률 시행규칙": "liquor",
    "도로법": "road",
    "도로법 시행령": "road",
    "도로법 시행규칙": "road",
}
CAFE_RESTAURANT_LAW_KEYWORDS = {
    "food": {
        "식품접객",
        "휴게음식",
        "일반음식",
        "제과점",
        "영업신고",
        "영업허가",
        "시설기준",
        "위생교육",
        "건강진단",
        "조리사",
        "조리판매",
        "영업자의 준수",
    },
    "liquor": {
        "주류 판매",
        "주류판매",
        "주류의 판매",
        "주류를 판매",
        "음식점",
        "일반음식점",
    },
    "road": {
        "도로점용",
        "점용허가",
        "점용 허가",
        "도로의 점용",
        "노상",
        "공개공지",
    },
}
CAFE_RESTAURANT_EXCLUDED_EASYLAW_KINDS = {
    "related_law_section",
    "card_news_section",
    "qna_section",
    "unknown_section",
}


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def estimate_prompt_tokens(chunk: dict[str, Any]) -> int:
    text = chunk.get("text", "")
    metadata = " ".join(
        str(chunk.get(key, ""))
        for key in ["chunk_id", "source_document_id", "source_type", "title", "section_path"]
    )
    return max(1, int((len(text) + len(metadata) + 2200) / 2.2))


def text_blob(chunk: dict[str, Any]) -> str:
    return " ".join(str(chunk.get(key, "")) for key in ["title", "section_path", "text"])


def cafe_restaurant_reason(chunk: dict[str, Any]) -> str:
    source_type = chunk.get("source_type", "")
    source_record_id = str(chunk.get("source_record_id", ""))
    if source_type == "gov24" and source_record_id in CAFE_RESTAURANT_GOV24_RECORDS:
        return "cafe_restaurant:gov24_core"
    if (
        source_type == "easylaw"
        and source_record_id in CAFE_RESTAURANT_EASYLAW_RECORDS
        and chunk.get("chunk_kind") not in CAFE_RESTAURANT_EXCLUDED_EASYLAW_KINDS
    ):
        return "cafe_restaurant:easylaw_core"
    if source_type == "law.go.kr":
        bucket = CAFE_RESTAURANT_LAW_BUCKETS.get(source_record_id, "")
        if bucket and any(keyword in text_blob(chunk) for keyword in CAFE_RESTAURANT_LAW_KEYWORDS[bucket]):
            return f"cafe_restaurant:law_{bucket}"
    return ""


def select_reason(
    chunk: dict[str, Any],
    *,
    profile: str,
    mode: str,
    target_tags: set[str],
    min_relevance: int,
    include_relevance: bool,
) -> str:
    if profile == "cafe_restaurant_core":
        return cafe_restaurant_reason(chunk)
    if mode == "all":
        return "mode_all"
    source_type = chunk.get("source_type", "")
    if source_type == "gov24":
        return "gov24_all"
    tags = set(chunk.get("scope_tags") or [])
    if tags & target_tags:
        return "scope_tag:" + ",".join(sorted(tags & target_tags))
    if include_relevance and int(chunk.get("relevance_score") or 0) >= min_relevance:
        return f"relevance>={min_relevance}"
    return ""


def priority(chunk: dict[str, Any], reason: str, profile: str) -> int:
    source_type = chunk.get("source_type", "")
    score = int(chunk.get("relevance_score") or 0)
    if profile == "cafe_restaurant_core":
        if reason == "cafe_restaurant:gov24_core":
            return 1200 + score
        if reason == "cafe_restaurant:easylaw_core":
            return 900 + score
        if reason == "cafe_restaurant:law_food":
            return 760 + score
        if reason == "cafe_restaurant:law_liquor":
            return 720 + score
        if reason == "cafe_restaurant:law_road":
            return 680 + score
    if source_type == "gov24":
        return 1000 + score
    if reason.startswith("scope_tag"):
        return 700 + score
    if source_type == "law.go.kr":
        return 500 + score
    return 300 + score


def build_queue(
    chunks: list[dict[str, Any]],
    *,
    profile: str,
    mode: str,
    target_tags: set[str],
    min_relevance: int,
    include_relevance: bool,
    source_types: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        if source_types and chunk.get("source_type") not in source_types:
            continue
        reason = select_reason(
            chunk,
            profile=profile,
            mode=mode,
            target_tags=target_tags,
            min_relevance=min_relevance,
            include_relevance=include_relevance,
        )
        if not reason:
            continue
        row = dict(chunk)
        row["queue_id"] = f"q_{len(rows) + 1:06d}"
        row["selection_reason"] = reason
        row["priority"] = priority(chunk, reason, profile)
        row["prompt_estimated_tokens"] = estimate_prompt_tokens(chunk)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            -int(row["priority"]),
            row.get("source_type", ""),
            row.get("source_document_id", ""),
            int(row.get("sequence") or 0),
            row.get("chunk_id", ""),
        )
    )
    for i, row in enumerate(rows, start=1):
        row["queue_id"] = f"q_{i:06d}"
    if limit:
        rows = rows[:limit]
    return rows


def write_manifest(path: Path, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    by_source = Counter(row.get("source_type", "") for row in rows)
    by_reason = Counter(row.get("selection_reason", "") for row in rows)
    total_prompt_tokens = sum(int(row.get("prompt_estimated_tokens") or 0) for row in rows)
    lines = [
        "# Claim Extraction Queue Manifest",
        "",
        "## Parameters",
        "",
        f"- profile: {args.profile}",
        f"- mode: {args.mode}",
        f"- include_relevance: {args.include_relevance}",
        f"- min_relevance: {args.min_relevance}",
        f"- target_tags: {', '.join(sorted(set(args.target_tag)))}",
        f"- source_types: {', '.join(args.source_type) if args.source_type else 'all'}",
        f"- limit: {args.limit or 'none'}",
        "",
        "## Totals",
        "",
        f"- queued_chunks: {len(rows)}",
        f"- source_documents: {len({row.get('source_document_id', '') for row in rows})}",
        f"- estimated_prompt_tokens: {total_prompt_tokens:,}",
        "",
        "## By Source",
        "",
    ]
    for key, value in sorted(by_source.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## By Selection Reason", ""])
    for key, value in sorted(by_reason.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## First 20", ""])
    for row in rows[:20]:
        lines.append(
            f"- {row['queue_id']} | priority={row['priority']} | "
            f"{row['source_type']} | score={row.get('relevance_score')} | "
            f"{row.get('title', '')} | {row['chunk_id']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare evidence chunks for LLM claim extraction.")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--profile", choices=["general", "cafe_restaurant_core"], default="general")
    parser.add_argument("--mode", choices=["focused", "all"], default="focused")
    parser.add_argument("--target-tag", action="append", default=sorted(DEFAULT_TARGET_TAGS))
    parser.add_argument("--include-relevance", action="store_true")
    parser.add_argument("--min-relevance", type=int, default=3)
    parser.add_argument("--source-type", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not args.evidence.exists():
        raise SystemExit(f"Missing evidence file: {args.evidence}")

    chunks = list(iter_jsonl(args.evidence))
    rows = build_queue(
        chunks,
        profile=args.profile,
        mode=args.mode,
        target_tags=set(args.target_tag),
        min_relevance=args.min_relevance,
        include_relevance=args.include_relevance,
        source_types=set(args.source_type),
        limit=args.limit,
    )
    write_jsonl(args.output, rows)
    write_manifest(args.manifest, rows, args)
    print(f"queued_chunks={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
