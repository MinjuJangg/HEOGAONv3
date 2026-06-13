from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from run_llm_claim_extraction import OUT, clean_text, iter_jsonl


GRAPH_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = GRAPH_ROOT.parents[1]
ROOT = WORKSPACE_ROOT
DEFAULT_CLAIMS = OUT / "nano_full_final.jsonl"
DEFAULT_EVIDENCE = OUT / "evidence_chunks.jsonl"
DEFAULT_RAW_HTML = ROOT / "data" / "raw" / "gov24" / "food_business_report.html"
DEFAULT_OUT_CLAIMS = OUT / "nano_full_final_gov24_canonical.jsonl"
DEFAULT_OUT_EVIDENCE = OUT / "evidence_chunks_augmented.jsonl"
DEFAULT_REPORT = OUT / "gov24_food_business_canonical_report.md"

SOURCE_DOCUMENT_ID = "gov24_food_business_report"
SOURCE_RECORD_ID = "food_business_report"
SOURCE_TYPE = "gov24"
SOURCE_URL = "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=14600000021&HighCtgCD=A09006&tp_seq=02"
RAW_PATH = "data/raw/gov24/food_business_report.html"
TITLE = "식품관련영업신고"


REQUIRED_NAME_RULES = [
    ("교육이수증", "교육이수증"),
    ("제조ㆍ가공하려는 식품 및 식품첨가물의 종류 및 제조방법설명서", "제조ㆍ가공하려는 식품 및 식품첨가물의 종류 및 제조방법설명서"),
    ("시설사용계약서", "시설사용계약서"),
    ("수질검사(시험)성적서", "먹는물 수질검사기관의 수질검사(시험)성적서"),
    ("유선 또는 도선사업 면허증 또는 신고필증", "유선 또는 도선사업 면허증 또는 신고필증"),
    ("안전시설등 완비증명서", "안전시설등 완비증명서"),
    ("식품자동판매기의 종류 및 설치장소가 적힌 서류", "식품자동판매기의 종류 및 설치장소가 적힌 서류"),
    ("수상레저사업 등록증", "수상레저사업 등록증"),
    ("국유재산 사용허가서", "국유재산 사용허가서"),
    ("도시철도시설 사용계약에 관한 서류", "도시철도시설 사용계약에 관한 서류"),
    ("예비군식당 운영계약에 관한 서류", "예비군식당 운영계약에 관한 서류"),
    ("별표 15의2에 따른 서류", "해당 영업장에서 영업을 할 수 있음을 증명하는 식품위생법 시행규칙 별표 15의2에 따른 서류"),
    ("어린이놀이시설 설치검사합격증", "어린이놀이시설 설치검사합격증 또는 어린이놀이시설 정기시설검사합격증"),
]

CHECK_NAME_RULES = [
    ("토지이용계획확인서", "토지이용계획확인서"),
    ("건축물대장", "건축물대장 또는 건축물 임시사용 승인서"),
    ("액화석유가스 사용시설완성검사증명서", "액화석유가스 사용시설완성검사증명서"),
    ("자동차등록증", "자동차등록증"),
    ("사업자등록증", "사업자등록증"),
    ("건강진단결과서", "건강진단결과서"),
]

APPLICATION_FORM_NAME = "식품 영업 신고서 (식품위생법 시행규칙 별지서식 37호)"
APPLICATION_FORM_TEXT = "식품 영업 신고서 ( 식품위생법 시행규칙 : 별지서식 37호 )"


def stable_hash(*parts: Any, length: int = 16) -> str:
    payload = "\u241f".join(str(part or "") for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def text_from_html(fragment: str) -> str:
    fragment = html.unescape(fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return clean_text(fragment)


def extract_li_items(block: str) -> list[str]:
    return [text_from_html(match) for match in re.findall(r"<li[^>]*>(.*?)</li>", block, flags=re.S | re.I)]


def block_between(text: str, start_pattern: str, end_pattern: str) -> str:
    start = re.search(start_pattern, text, flags=re.S | re.I)
    if not start:
        raise ValueError(f"Missing start pattern: {start_pattern}")
    end = re.search(end_pattern, text[start.end() :], flags=re.S | re.I)
    if not end:
        raise ValueError(f"Missing end pattern after: {start_pattern}")
    return text[start.end() : start.end() + end.start()]


def extract_gov24_items(raw_html: str) -> tuple[list[str], list[str]]:
    required_block = block_between(
        raw_html,
        r'<h4[^>]*id="RequiredDoc"[^>]*>.*?</h4>',
        r'<h4[^>]*>\s*민원인이 제출하지 않아도 되는 서류',
    )
    check_block = block_between(
        raw_html,
        r'<h4[^>]*>\s*민원인이 제출하지 않아도 되는 서류.*?</h4>',
        r"</ul>\s*</ul>",
    )
    return extract_li_items(required_block), extract_li_items(check_block)


def name_from_rules(item: str, rules: list[tuple[str, str]]) -> str:
    for needle, name in rules:
        if needle in item:
            return name
    raise ValueError(f"No canonical name rule matched item: {item}")


def canonical_chunk(
    *,
    chunk_id: str,
    chunk_kind: str,
    section_path: str,
    text: str,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "source_document_id": SOURCE_DOCUMENT_ID,
        "source_type": SOURCE_TYPE,
        "source_record_id": SOURCE_RECORD_ID,
        "source_url": SOURCE_URL,
        "raw_path": RAW_PATH,
        "title": TITLE,
        "section_path": section_path,
        "chunk_kind": chunk_kind,
        "text": text,
        "char_length": len(text),
        "token_estimate": max(1, int(len(text) / 2.2)),
        "extraction_method": "gov24_html_list_parser",
    }


def canonical_claim(
    *,
    claim_id: str,
    predicate: str,
    object_type: str,
    object_name: str,
    chunk_id: str,
    evidence_text: str,
    section_path: str,
    condition_text: str = "",
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "subject_type": "permit_service",
        "subject_name": TITLE,
        "predicate": predicate,
        "object_type": object_type,
        "object_name": object_name,
        "assertion_level": "explicit",
        "authority_level": "official",
        "review_status": "official_document",
        "confidence": 0.95,
        "condition_text": condition_text,
        "evidence_text": evidence_text,
        "source_document_id": SOURCE_DOCUMENT_ID,
        "chunk_id": chunk_id,
        "source_type": SOURCE_TYPE,
        "source_record_id": SOURCE_RECORD_ID,
        "source_url": SOURCE_URL,
        "raw_path": RAW_PATH,
        "title": TITLE,
        "section_path": section_path,
        "extraction_method": "gov24_html_list_parser",
        "model": "",
        "validation_errors": [],
    }


def should_replace_claim(claim: dict[str, Any]) -> bool:
    return (
        claim.get("source_document_id") == SOURCE_DOCUMENT_ID
        and claim.get("subject_name") == TITLE
        and claim.get("predicate") in {"requires_document", "needs_check"}
    )


def build_canonical_rows(raw_html: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    required_items, check_items = extract_gov24_items(raw_html)
    chunks: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for idx, item in enumerate(required_items, start=1):
        name = name_from_rules(item, REQUIRED_NAME_RULES)
        chunk_id = f"evchunk_gov24_food_business_required_{idx:02d}"
        section_path = f"{TITLE} > 민원인이 제출해야하는 서류 > {name}"
        chunks.append(
            canonical_chunk(
                chunk_id=chunk_id,
                chunk_kind="gov24_required_document_item",
                section_path=section_path,
                text=item,
            )
        )
        claims.append(
            canonical_claim(
                claim_id=f"claim_gov24_food_business_required_{stable_hash(name, idx)}",
                predicate="requires_document",
                object_type="document",
                object_name=name,
                chunk_id=chunk_id,
                evidence_text=item,
                section_path=section_path,
            )
        )

    form_chunk_id = "evchunk_gov24_food_business_application_form"
    form_section_path = f"{TITLE} > 서비스 개요 > 신청서"
    chunks.append(
        canonical_chunk(
            chunk_id=form_chunk_id,
            chunk_kind="gov24_application_form",
            section_path=form_section_path,
            text=APPLICATION_FORM_TEXT,
        )
    )
    claims.append(
        canonical_claim(
            claim_id=f"claim_gov24_food_business_application_form_{stable_hash(APPLICATION_FORM_NAME)}",
            predicate="requires_document",
            object_type="document",
            object_name=APPLICATION_FORM_NAME,
            chunk_id=form_chunk_id,
            evidence_text=APPLICATION_FORM_TEXT,
            section_path=form_section_path,
            condition_text="신청서",
        )
    )

    for idx, item in enumerate(check_items, start=1):
        name = name_from_rules(item, CHECK_NAME_RULES)
        chunk_id = f"evchunk_gov24_food_business_official_check_{idx:02d}"
        section_path = f"{TITLE} > 민원인이 제출하지 않아도 되는 서류 > {name}"
        chunks.append(
            canonical_chunk(
                chunk_id=chunk_id,
                chunk_kind="gov24_official_check_item",
                section_path=section_path,
                text=item,
            )
        )
        claims.append(
            canonical_claim(
                claim_id=f"claim_gov24_food_business_check_{stable_hash(name, idx)}",
                predicate="needs_check",
                object_type="check_item",
                object_name=name,
                chunk_id=chunk_id,
                evidence_text=item,
                section_path=section_path,
                condition_text="담당공무원이 확인",
            )
        )

    stats = {
        "required_items": len(required_items),
        "application_form_items": 1,
        "official_check_items": len(check_items),
        "canonical_claims": len(claims),
        "canonical_chunks": len(chunks),
    }
    return chunks, claims, stats


def report_text(stats: dict[str, Any], canonical_claims: list[dict[str, Any]], removed: list[dict[str, Any]]) -> str:
    required = [c for c in canonical_claims if c["predicate"] == "requires_document"]
    checks = [c for c in canonical_claims if c["predicate"] == "needs_check"]
    required_lines = "\n".join(f"- {c['object_name']}" for c in required)
    check_lines = "\n".join(f"- {c['object_name']}" for c in checks)
    removed_lines = "\n".join(
        f"- {c.get('predicate')} | {c.get('object_name')} | {c.get('section_path')}"
        for c in removed
    )
    return f"""# Gov24 Food Business Canonicalization Report

## Counts

- required_document_items_from_html: {stats["required_items"]}
- application_form_items: {stats["application_form_items"]}
- official_check_items_from_html: {stats["official_check_items"]}
- canonical_claims_added: {stats["canonical_claims"]}
- canonical_evidence_chunks_added: {stats["canonical_chunks"]}
- replaced_llm_claims: {len(removed)}

## Canonical Required Documents

{required_lines}

## Canonical Official Check Items

{check_lines}

## Replaced LLM Claims

{removed_lines}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace Gov24 food business document claims with canonical HTML-list claims.")
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--raw-html", type=Path, default=DEFAULT_RAW_HTML)
    parser.add_argument("--out-claims", type=Path, default=DEFAULT_OUT_CLAIMS)
    parser.add_argument("--out-evidence", type=Path, default=DEFAULT_OUT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    raw_html = args.raw_html.read_text(encoding="utf-8")
    canonical_chunks, canonical_claims, stats = build_canonical_rows(raw_html)

    original_claims = list(iter_jsonl(args.claims))
    removed = [claim for claim in original_claims if should_replace_claim(claim)]
    kept_claims = [claim for claim in original_claims if not should_replace_claim(claim)]
    write_jsonl(args.out_claims, kept_claims + canonical_claims)

    original_evidence = list(iter_jsonl(args.evidence))
    existing_chunk_ids = {chunk.get("chunk_id") for chunk in original_evidence}
    new_chunks = [chunk for chunk in canonical_chunks if chunk["chunk_id"] not in existing_chunk_ids]
    write_jsonl(args.out_evidence, original_evidence + new_chunks)

    args.report.write_text(report_text(stats, canonical_claims, removed), encoding="utf-8")

    print(f"kept_claims={len(kept_claims)} removed_claims={len(removed)} canonical_claims={len(canonical_claims)} out_claims={args.out_claims}")
    print(f"original_evidence={len(original_evidence)} new_chunks={len(new_chunks)} out_evidence={args.out_evidence}")
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
