from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from run_llm_claim_extraction import (
    ALLOWED_PAIRS,
    OUT,
    SYSTEM_PROMPT,
    append_jsonl,
    call_model,
    choose_provider,
    clean_text,
    enrich_claim,
    iter_jsonl,
    load_default_env_files,
    normalize_raw_claim,
    parse_json_object,
    provider_config,
    write_json,
)


DEFAULT_EVIDENCE = OUT / "evidence_chunks.jsonl"
DEFAULT_CLAIMS = OUT / "llm_claims.jsonl"
DEFAULT_REPAIRED = OUT / "llm_claims_repaired.jsonl"
DEFAULT_FINAL = OUT / "llm_claims_final.jsonl"
DEFAULT_CACHE_DIR = OUT / "llm_repair_cache"
DEFAULT_REPORT = OUT / "llm_claim_repair_report.md"


REPAIR_PROMPT_TEMPLATE = """Repair invalid GraphRAG claims extracted from this source chunk.

Your job:
- Return only corrected replacement claims for the invalid claims below.
- If a claim cannot be repaired from the chunk text, omit it.
- Do not invent new facts.
- evidence_text must be an exact substring copied from the chunk.
- Use only allowed predicate/type pairs.

Allowed predicate/type pairs:
{allowed_pairs}

Common repairs:
- document -> maps_to -> admin_business_type is invalid. If it is a submitted document, use permit_service -> requires_document -> document.
- permit_service -> triggers -> condition_module/admin_business_type/risk_flag is invalid. For official checks use permit_service -> needs_check -> check_item. For risk warnings use permit_service -> raises_risk -> risk_flag.
- department_function -> needs_check -> check_item is invalid. Use permit_service -> needs_check -> check_item.
- If only evidence_text is invalid, keep the claim meaning but replace evidence_text with the exact matching excerpt.
- Do not output has_source or supported_by claims.

Return exactly:
{{
  "claims": [
    {{
      "subject_type": "permit_service",
      "subject_name": "{title}",
      "predicate": "requires_document",
      "object_type": "document",
      "object_name": "교육이수증",
      "assertion_level": "explicit",
      "authority_level": "{authority_level}",
      "review_status": "official_document",
      "confidence": 0.8,
      "condition_text": "",
      "evidence_text": "exact excerpt copied from chunk"
    }}
  ]
}}

Source metadata:
- chunk_id: {chunk_id}
- source_document_id: {source_document_id}
- source_type: {source_type}
- authority_level: {authority_level}
- title: {title}
- section_path: {section_path}

Invalid claims to repair:
{invalid_claims_json}

Chunk:
{chunk_text}
"""


def allowed_pairs_text() -> str:
    lines: list[str] = []
    for predicate, pairs in sorted(ALLOWED_PAIRS.items()):
        if predicate in {"has_source", "supported_by"}:
            continue
        for subject_type, object_type in sorted(pairs):
            lines.append(f"- {predicate}: {subject_type} -> {object_type}")
    return "\n".join(lines)


def claim_for_prompt(claim: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "claim_id",
        "subject_type",
        "subject_name",
        "predicate",
        "object_type",
        "object_name",
        "condition_text",
        "evidence_text",
        "validation_errors",
    ]
    return {field: claim.get(field, "") for field in fields}


def fold_for_match(value: Any) -> str:
    return "".join(ch.casefold() for ch in clean_text(value) if ch.isalnum())


def clean_with_fold_map(value: Any) -> tuple[str, str, list[int]]:
    text = clean_text(value)
    folded: list[str] = []
    index_map: list[int] = []
    for idx, char in enumerate(text):
        if char.isalnum():
            folded.append(char.casefold())
            index_map.append(idx)
    return text, "".join(folded), index_map


def expand_excerpt(text: str, start: int, end: int, before: int = 80, after: int = 180) -> str:
    left = max(0, start - before)
    right = min(len(text), end + after)
    for idx in range(start - 1, left, -1):
        if text[idx] in ".!?;:()[]{}":
            left = idx + 1
            break
    for idx in range(end, right):
        if text[idx] in ".!?;:()[]{}":
            right = idx + 1
            break
    return clean_text(text[left:right])


def excerpt_for_needles(chunk: dict[str, Any], needles: list[Any]) -> str:
    chunk_text = clean_text(chunk.get("text", ""))
    if not chunk_text:
        return ""

    for needle in needles:
        needle_text = clean_text(needle)
        if not needle_text:
            continue
        idx = chunk_text.find(needle_text)
        if idx >= 0:
            return expand_excerpt(chunk_text, idx, idx + len(needle_text))

    _, folded_chunk, index_map = clean_with_fold_map(chunk_text)
    if not folded_chunk:
        return ""
    for needle in needles:
        folded_needle = fold_for_match(needle)
        if len(folded_needle) < 3:
            continue
        pos = folded_chunk.find(folded_needle)
        if pos < 0:
            continue
        start = index_map[pos]
        end = index_map[pos + len(folded_needle) - 1] + 1
        return expand_excerpt(chunk_text, start, end)
    return ""


GENERIC_FOLDED_TERMS = {
    fold_for_match("\uc11c\ube44\uc2a4 \uac1c\uc694"),
    fold_for_match("\uad6c\ube44\uc11c\ub958 \uc788\uc74c"),
    fold_for_match("\ud558\ub2e8 \ucc38\uc870"),
    fold_for_match("\ucc98\ub9ac\uae30\uac04"),
    fold_for_match("\uc218\uc218\ub8cc \uc5c6\uc74c"),
}


def is_generic_only_claim(claim: dict[str, Any]) -> bool:
    folded = fold_for_match(
        " ".join(
            [
                clean_text(claim.get("object_name", "")),
                clean_text(claim.get("condition_text", "")),
                clean_text(claim.get("evidence_text", "")),
            ]
        )
    )
    return any(term and term in folded for term in GENERIC_FOLDED_TERMS)


def base_repair_candidate(claim: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "subject_type",
        "subject_name",
        "predicate",
        "object_type",
        "object_name",
        "assertion_level",
        "authority_level",
        "review_status",
        "confidence",
        "condition_text",
        "evidence_text",
    ]
    return {field: claim.get(field, "") for field in fields}


def set_evidence(candidate: dict[str, Any], claim: dict[str, Any], chunk: dict[str, Any]) -> bool:
    evidence = excerpt_for_needles(
        chunk,
        [
            candidate.get("evidence_text", ""),
            candidate.get("object_name", ""),
            claim.get("evidence_text", ""),
            claim.get("object_name", ""),
            claim.get("subject_name", ""),
        ],
    )
    if not evidence:
        return False
    candidate["evidence_text"] = evidence
    return True


def deterministic_repair_claim(claim: dict[str, Any], chunk: dict[str, Any], model: str) -> dict[str, Any] | None:
    errors = set(claim.get("validation_errors") or [])
    if not errors:
        return None

    candidate = normalize_raw_claim(base_repair_candidate(claim))
    normalized = enrich_claim(candidate, chunk, model)
    normalized["extraction_method"] = "deterministic_repair"
    normalized["repair_source_claim_ids"] = [claim.get("claim_id", "")]
    if not normalized.get("validation_errors"):
        return normalized

    subject_type = clean_text(claim.get("subject_type", ""))
    predicate = clean_text(claim.get("predicate", ""))
    object_type = clean_text(claim.get("object_type", ""))
    title = clean_text(chunk.get("title", "")) or clean_text(claim.get("subject_name", ""))

    if errors == {"evidence_not_substring"}:
        if not set_evidence(candidate, claim, chunk):
            return None
    elif "invalid_type_pair" in errors:
        if is_generic_only_claim(claim):
            return None
        if predicate == "triggers" and subject_type == "permit_service" and object_type == "condition_module":
            candidate["subject_type"] = "condition_module"
            candidate["subject_name"] = clean_text(claim.get("object_name", ""))
            candidate["predicate"] = "triggers"
            candidate["object_type"] = "permit_service"
            candidate["object_name"] = clean_text(claim.get("subject_name", "")) or title
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate == "triggers" and subject_type == "permit_service" and object_type == "risk_flag":
            candidate["predicate"] = "raises_risk"
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate == "needs_check" and object_type == "check_item":
            candidate["subject_type"] = "permit_service"
            candidate["subject_name"] = title
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate == "requires_document" and object_type == "document":
            candidate["subject_type"] = "permit_service"
            candidate["subject_name"] = title
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate == "maps_to" and subject_type == "document" and object_type == "admin_business_type":
            candidate["subject_type"] = "permit_service"
            candidate["subject_name"] = title
            candidate["predicate"] = "requires_document"
            candidate["object_type"] = "document"
            candidate["object_name"] = clean_text(claim.get("subject_name", ""))
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate == "triggers" and subject_type == "permit_service" and object_type == "check_item":
            candidate["predicate"] = "needs_check"
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate == "requires_permit" and subject_type == "permit_service" and object_type == "admin_business_type":
            candidate["subject_type"] = "admin_business_type"
            candidate["subject_name"] = clean_text(claim.get("object_name", ""))
            candidate["predicate"] = "requires_permit"
            candidate["object_type"] = "permit_service"
            candidate["object_name"] = clean_text(claim.get("subject_name", "")) or title
            if not set_evidence(candidate, claim, chunk):
                return None
        else:
            return None
    elif "invalid_predicate" in errors:
        if predicate in {"required_document", "requires_documents"}:
            candidate["predicate"] = "requires_document"
            if not set_evidence(candidate, claim, chunk):
                return None
        elif predicate in {"need_check", "requires_check"}:
            candidate["predicate"] = "needs_check"
            if not set_evidence(candidate, claim, chunk):
                return None
        else:
            return None
    else:
        return None

    candidate["assertion_level"] = candidate.get("assertion_level") or "explicit"
    candidate["review_status"] = "official_document"
    candidate["confidence"] = min(float(candidate.get("confidence") or 0.8), 0.8)
    repaired = enrich_claim(candidate, chunk, model)
    repaired["extraction_method"] = "deterministic_repair"
    repaired["repair_source_claim_ids"] = [claim.get("claim_id", "")]
    if repaired.get("validation_errors"):
        return None
    return repaired


def repair_prompt(chunk: dict[str, Any], invalid_claims: list[dict[str, Any]]) -> str:
    return REPAIR_PROMPT_TEMPLATE.format(
        allowed_pairs=allowed_pairs_text(),
        title=chunk.get("title", ""),
        authority_level=chunk.get("authority_level", "official"),
        chunk_id=chunk.get("chunk_id", ""),
        source_document_id=chunk.get("source_document_id", ""),
        source_type=chunk.get("source_type", ""),
        section_path=chunk.get("section_path", ""),
        invalid_claims_json=json.dumps(
            [claim_for_prompt(claim) for claim in invalid_claims],
            ensure_ascii=False,
            indent=2,
        ),
        chunk_text=chunk.get("text", ""),
    )


def dedupe_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for claim in claims:
        key = (
            claim.get("chunk_id", ""),
            claim.get("subject_type", ""),
            clean_text(claim.get("subject_name", "")),
            claim.get("predicate", ""),
            claim.get("object_type", ""),
            clean_text(claim.get("object_name", "")),
            clean_text(claim.get("evidence_text", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(claim)
    return out


def write_final_outputs(
    *,
    original_claims: list[dict[str, Any]],
    repaired_claims: list[dict[str, Any]],
    final_path: Path,
    report_path: Path,
    raw_groups: int,
    deterministic_repaired: int = 0,
    llm_groups: int = 0,
) -> None:
    original_valid = [claim for claim in original_claims if not claim.get("validation_errors")]
    repaired_valid = [claim for claim in repaired_claims if not claim.get("validation_errors")]
    final_claims = dedupe_claims(original_valid + repaired_valid)

    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(
        "".join(json.dumps(claim, ensure_ascii=False) + "\n" for claim in final_claims),
        encoding="utf-8",
    )

    before_errors = Counter(error for claim in original_claims for error in claim.get("validation_errors", []))
    repaired_errors = Counter(error for claim in repaired_claims for error in claim.get("validation_errors", []))
    by_predicate = Counter(claim.get("predicate", "") for claim in final_claims)
    lines = [
        "# LLM Claim Repair Report",
        "",
        "## Totals",
        "",
        f"- original_claims: {len(original_claims)}",
        f"- original_valid_claims: {len(original_valid)}",
        f"- original_invalid_claims: {len(original_claims) - len(original_valid)}",
        f"- repaired_claims: {len(repaired_claims)}",
        f"- repaired_valid_claims: {len(repaired_valid)}",
        f"- deterministic_repaired_claims: {deterministic_repaired}",
        f"- final_valid_claims: {len(final_claims)}",
        f"- repaired_chunk_groups: {raw_groups}",
        f"- llm_repair_chunk_groups: {llm_groups}",
        "",
        "## Original Error Types",
        "",
    ]
    for key, value in sorted(before_errors.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Remaining Repaired Error Types", ""])
    if repaired_errors:
        for key, value in sorted(repaired_errors.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none: 0")
    lines.extend(["", "## Final Predicates", ""])
    for key, value in sorted(by_predicate.items()):
        lines.append(f"- {key}: {value}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair invalid LLM claims using the original evidence chunks.")
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--repaired-output", type=Path, default=DEFAULT_REPAIRED)
    parser.add_argument("--final-output", type=Path, default=DEFAULT_FINAL)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--env-file", type=Path, action="append", default=[])
    parser.add_argument("--limit", type=int, default=0, help="Limit number of chunk groups to repair.")
    parser.add_argument("--max-claims", type=int, default=8)
    parser.add_argument("--max-output-tokens", type=int, default=4000)
    parser.add_argument("--reasoning-effort", default="")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--retry", type=int, default=2)
    parser.add_argument("--json-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--deterministic-only", action="store_true", help="Run only rule-based repairs; do not call the LLM.")
    args = parser.parse_args()

    load_default_env_files(args.env_file)
    provider = choose_provider("auto")
    api_key, model, base_url = provider_config(provider)
    if not api_key and not args.dry_run:
        raise SystemExit("Missing API key. Put GMS_API_KEY in minju/graph/.env.gms.")

    evidence_by_chunk = {chunk["chunk_id"]: chunk for chunk in iter_jsonl(args.evidence) or []}
    original_claims: list[dict[str, Any]] = []
    for claim in iter_jsonl(args.claims) or []:
        chunk = evidence_by_chunk.get(claim.get("chunk_id", ""))
        if not chunk:
            original_claims.append(claim)
            continue
        revalidated = enrich_claim(normalize_raw_claim(claim), chunk, model)
        revalidated["extraction_method"] = claim.get("extraction_method", "llm")
        original_claims.append(revalidated)

    invalid_by_chunk: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in original_claims:
        if claim.get("validation_errors"):
            invalid_by_chunk[claim.get("chunk_id", "")].append(claim)

    groups = [(chunk_id, claims) for chunk_id, claims in invalid_by_chunk.items() if chunk_id in evidence_by_chunk]
    if args.limit:
        groups = groups[: args.limit]

    print(f"invalid_claims={sum(len(claims) for _, claims in groups)} chunk_groups={len(groups)}")
    if args.dry_run:
        write_final_outputs(
            original_claims=original_claims,
            repaired_claims=[],
            final_path=args.final_output,
            report_path=args.report,
            raw_groups=0,
        )
        return

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    if args.repaired_output.exists():
        args.repaired_output.unlink()

    repaired_claims: list[dict[str, Any]] = []
    remaining_by_chunk: dict[str, list[dict[str, Any]]] = defaultdict(list)
    deterministic_repairs: list[dict[str, Any]] = []
    for chunk_id, invalid_claims in groups:
        chunk = evidence_by_chunk[chunk_id]
        for claim in invalid_claims:
            repaired = deterministic_repair_claim(claim, chunk, model)
            if repaired:
                deterministic_repairs.append(repaired)
            else:
                remaining_by_chunk[chunk_id].append(claim)

    if deterministic_repairs:
        append_jsonl(args.repaired_output, deterministic_repairs)
        repaired_claims.extend(deterministic_repairs)

    groups_to_llm = [(chunk_id, claims) for chunk_id, claims in groups if remaining_by_chunk.get(chunk_id)]
    groups_to_llm = [(chunk_id, remaining_by_chunk[chunk_id]) for chunk_id, _ in groups_to_llm]
    print(
        "deterministic_repaired="
        f"{len(deterministic_repairs)} remaining_invalid={sum(len(claims) for _, claims in groups_to_llm)} "
        f"remaining_chunk_groups={len(groups_to_llm)}"
    )
    if args.deterministic_only:
        write_final_outputs(
            original_claims=original_claims,
            repaired_claims=repaired_claims,
            final_path=args.final_output,
            report_path=args.report,
            raw_groups=len(groups),
            deterministic_repaired=len(deterministic_repairs),
            llm_groups=0,
        )
        print(f"repaired_claims={len(repaired_claims)} final={args.final_output}")
        return

    call_args = SimpleNamespace(
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        reasoning_effort=args.reasoning_effort,
        timeout=args.timeout,
        json_mode=args.json_mode,
    )
    for idx, (chunk_id, invalid_claims) in enumerate(groups_to_llm, start=1):
        chunk = evidence_by_chunk[chunk_id]
        cache_path = args.cache_dir / f"{chunk_id}.json"
        prompt = repair_prompt(chunk, invalid_claims)
        last_error = ""
        for attempt in range(1, args.retry + 1):
            try:
                content, raw_response = call_model(call_args, provider, api_key, model, base_url, prompt)
                parsed = parse_json_object(content)
                raw_claims = parsed.get("claims") or []
                if not isinstance(raw_claims, list):
                    raw_claims = []
                repairs: list[dict[str, Any]] = []
                for claim in raw_claims:
                    if not isinstance(claim, dict):
                        continue
                    repaired = enrich_claim(normalize_raw_claim(claim), chunk, model)
                    repaired["extraction_method"] = "llm_repair"
                    repaired["repair_source_claim_ids"] = [c.get("claim_id", "") for c in invalid_claims]
                    repairs.append(repaired)
                raw_row = {
                    "chunk_id": chunk_id,
                    "input_invalid_claim_ids": [c.get("claim_id", "") for c in invalid_claims],
                    "provider": provider,
                    "model": model,
                    "raw_claims": raw_claims,
                    "repaired_claims_count": len(repairs),
                    "raw_response": raw_response,
                }
                write_json(cache_path, raw_row)
                if repairs:
                    append_jsonl(args.repaired_output, repairs)
                    repaired_claims.extend(repairs)
                invalid_count = sum(1 for claim in repairs if claim.get("validation_errors"))
                print(f"[{idx}/{len(groups_to_llm)}] {chunk_id} repaired={len(repairs)} invalid={invalid_count}")
                break
            except Exception as exc:  # noqa: BLE001
                last_error = repr(exc)
                wait = min(12.0, args.sleep * (2**attempt))
                print(f"[retry {attempt}/{args.retry}] {chunk_id}: {last_error}; sleep={wait}")
                time.sleep(wait)
        else:
            error_row = {
                "chunk_id": chunk_id,
                "input_invalid_claim_ids": [c.get("claim_id", "") for c in invalid_claims],
                "provider": provider,
                "model": model,
                "error": last_error,
            }
            write_json(cache_path, error_row)
        time.sleep(args.sleep)

    write_final_outputs(
        original_claims=original_claims,
        repaired_claims=repaired_claims,
        final_path=args.final_output,
        report_path=args.report,
        raw_groups=len(groups),
        deterministic_repaired=len(deterministic_repairs),
        llm_groups=len(groups_to_llm),
    )
    print(f"repaired_claims={len(repaired_claims)} final={args.final_output}")


if __name__ == "__main__":
    main()
