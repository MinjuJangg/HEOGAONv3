from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


GRAPH_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = GRAPH_ROOT.parents[1]
ROOT = WORKSPACE_ROOT
PROCESSED = WORKSPACE_ROOT / "data" / "processed"
OUT = GRAPH_ROOT / "output" / "intermediate"
RAW_MARKER = ("data", "raw")


CLAIM_KEYWORDS = [
    "창업",
    "영업",
    "신고",
    "허가",
    "등록",
    "지정",
    "면허",
    "신청",
    "제출",
    "서류",
    "구비서류",
    "교육",
    "위생",
    "건강진단",
    "건축물대장",
    "토지이용계획",
    "용도변경",
    "시설기준",
    "옥외광고",
    "광고물",
    "간판",
    "도로점용",
    "통신판매",
    "전자상거래",
    "건강기능식품",
    "담배",
    "체육시설",
    "노래연습장",
    "공중위생",
    "미용",
    "세탁",
    "일반음식점",
    "휴게음식점",
    "제과점",
    "즉석판매",
    "식품접객",
    "주류",
    "음주행위",
    "소방",
    "안전시설",
    "전기안전",
    "액화석유가스",
    "LPG",
    "지하수",
    "어린이놀이시설",
    "음식판매자동차",
    "사업자등록",
    "임대차",
]


GOV24_SECTION_MARKERS = [
    "서비스 개요",
    "기본정보",
    "신청 방법 및 절차",
    "제출 서류",
    "민원인이 제출해야하는 서류",
    "민원인이 제출하지 않아도 되는 서류",
    "부가정보",
    "근거법령",
    "정보 변경 내역",
]

GOV24_DROP_SECTION_NAMES = {"정보 변경 내역"}

GOV24_TRAILING_MARKERS = [
    "이 페이지에 만족하시나요?",
    "국민소통채널",
    "디지털증명",
    "정부24 안내",
]

EASYLAW_TRAILING_MARKERS = [
    "이 정보는 20",
    "생활법령정보는 법적 효력을 갖는",
    "위 내용에 대한 홈페이지 개선의견",
    "하단 영역",
    "개인정보처리방침",
]

BOILERPLATE_PATTERNS = [
    "혜택알리미",
    "이 페이지에 만족하시나요",
    "국민소통채널",
    "개인정보처리방침",
    "홈페이지 개선의견",
    "본문 바로가기",
    "메인메뉴 바로가기",
    "검색어 입력",
    "전체 PDF 저장",
    "조회수:",
    "추천수:",
    "새소식 상세 내용",
    "100문 100답 목록",
    "자바스크립트가 지원되지 않아",
    "최근 본 법령정보",
    "팝업 배경",
]


def stable_id(prefix: str, *parts: str) -> str:
    raw = "||".join(str(part).strip() for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:14]}"


def slug(value: str, *, fallback: str = "document") -> str:
    text = clean_text(value)
    text = re.sub(r"[^\w가-힣ㆍ·]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"</?a\b[^>]*>", " ", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_after_markers(text: str, markers: list[str]) -> str:
    end = len(text)
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            end = min(end, idx)
    return clean_text(text[:end])


def resolve_workspace_path(raw_path: str) -> Path | None:
    if not raw_path:
        return None

    path = Path(raw_path)
    if path.exists():
        return path

    normalized = raw_path.replace("\\", "/")
    marker = "/".join(RAW_MARKER) + "/"
    marker_idx = normalized.find(marker)
    if marker_idx != -1:
        candidate = ROOT / Path(normalized[marker_idx:])
        if candidate.exists():
            return candidate

    candidate = ROOT / raw_path
    if candidate.exists():
        return candidate

    return None


def portable_raw_path(raw_path: str) -> str:
    path = resolve_workspace_path(raw_path)
    if path:
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    normalized = (raw_path or "").replace("\\", "/")
    marker = "/".join(RAW_MARKER) + "/"
    marker_idx = normalized.find(marker)
    if marker_idx != -1:
        return normalized[marker_idx:]
    return raw_path or ""


def iter_jsonl(path: Path):
    if not path.exists():
        return
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


def relevance_score(text: str) -> int:
    return sum(1 for keyword in CLAIM_KEYWORDS if keyword in text)


def scope_tags(text: str) -> list[str]:
    tags = []
    groups = {
        "food_business": ["식품", "음식점", "휴게음식점", "일반음식점", "제과점", "식품접객"],
        "hygiene": ["위생", "건강진단", "교육"],
        "ecommerce": ["통신판매", "전자상거래", "온라인"],
        "signage": ["옥외광고", "광고물", "간판"],
        "road": ["도로점용", "도로ㆍ보도", "도로·보도"],
        "building": ["건축물", "용도변경", "토지이용계획"],
        "safety": ["소방", "안전시설", "전기안전", "액화석유가스", "LPG", "어린이놀이시설"],
        "liquor": ["주류", "음주행위", "주점"],
        "business_registration": ["사업자등록"],
    }
    for tag, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tags


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 2.2))


def chunk_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = max(
                text.rfind("다. ", start, end),
                text.rfind(". ", start, end),
                text.rfind(") ", start, end),
                text.rfind(" ", start, end),
            )
            if boundary > start + max_chars * 0.62:
                end = boundary + 1
        chunk = clean_text(text[start:end])
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def add_chunk(
    rows: list[dict[str, Any]],
    *,
    source_document_id: str,
    source_type: str,
    source_record_id: str,
    authority_level: str,
    title: str,
    section_path: str,
    source_url: str,
    raw_path: str,
    chunk_kind: str,
    sequence: int,
    text: str,
    min_chars: int,
) -> None:
    text = clean_text(text)
    if len(text) < min_chars:
        return

    chunk_id = stable_id("evchunk", source_document_id, section_path, sequence, text[:160])
    rows.append(
        {
            "chunk_id": chunk_id,
            "source_document_id": source_document_id,
            "source_type": source_type,
            "source_record_id": source_record_id,
            "authority_level": authority_level,
            "title": clean_text(title),
            "section_path": clean_text(section_path),
            "source_url": source_url or "",
            "raw_path": portable_raw_path(raw_path),
            "chunk_kind": chunk_kind,
            "sequence": sequence,
            "char_len": len(text),
            "estimated_tokens": estimate_tokens(text),
            "relevance_score": relevance_score(text),
            "scope_tags": scope_tags(text),
            "text": text,
        }
    )


def source_document_id(source_type: str, *parts: str) -> str:
    readable = "_".join(slug(part) for part in parts if clean_text(part))
    if readable:
        return f"{source_type}_{readable}"
    return stable_id(f"{source_type}_source", *parts)


def split_gov24_sections(text: str) -> list[tuple[str, str]]:
    text = strip_after_markers(clean_text(text), GOV24_TRAILING_MARKERS)
    if not text:
        return []

    positions = []
    for marker in GOV24_SECTION_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            positions.append((idx, marker))
    positions = sorted(set(positions))
    if not positions:
        return [("full", text)]

    sections: list[tuple[str, str]] = []
    for i, (idx, marker) in enumerate(positions):
        if marker in GOV24_DROP_SECTION_NAMES:
            continue
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        section_text = clean_text(text[idx:end])
        if section_text:
            sections.append((marker, section_text))
    return sections


def build_gov24_chunks(max_chars: int, overlap: int, min_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in iter_jsonl(PROCESSED / "gov24_permit_pages.jsonl") or []:
        source_record_id = obj.get("id", "")
        title = obj.get("name", source_record_id)
        doc_id = source_document_id("gov24", source_record_id)
        for section_name, section_text in split_gov24_sections(obj.get("text", "")):
            section_path = f"{title} > {section_name}"
            for i, text in enumerate(chunk_text(section_text, max_chars=max_chars, overlap=overlap), start=1):
                add_chunk(
                    rows,
                    source_document_id=doc_id,
                    source_type="gov24",
                    source_record_id=source_record_id,
                    authority_level="official",
                    title=title,
                    section_path=section_path,
                    source_url=obj.get("source_url", ""),
                    raw_path=obj.get("raw_path", ""),
                    chunk_kind=section_name,
                    sequence=i,
                    text=text,
                    min_chars=min_chars,
                )
    return rows


def extract_html_main_text(raw_path: str) -> str:
    path = resolve_workspace_path(raw_path)
    if path is None:
        return ""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    html = path.read_text(encoding="utf-8", errors="ignore")
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    element = soup.select_one("#contents") or soup.select_one("#content") or soup.body
    if not element:
        return ""
    return clean_text(element.get_text(" ", strip=True))


def easylaw_page_kind(obj: dict[str, Any]) -> str:
    title = clean_text(obj.get("page_title", ""))
    url = obj.get("source_url", "")
    if "OnhunqueansLstPopRetrieve" in url:
        return "qna_list"
    if "menuType=onhunqna" in url or "100문 100답" in title:
        return "qna"
    if "menuType=easy" in url or "카드뉴스" in title:
        return "card_news"
    if "menuType=lsi" in url or title == "관련법령":
        return "related_law"
    if title == "○":
        return "unknown"
    return "body"


def trim_easylaw_text(text: str, page_title: str) -> str:
    text = clean_text(text)
    if not text:
        return ""
    if "본문 영역" in text:
        text = text[text.find("본문 영역") + len("본문 영역") :]
    elif page_title and page_title != "○" and page_title in text:
        text = text[text.find(page_title) :]

    text = re.sub(r"^본문\s+100문\s+100답\s+카드뉴스\s+관련법령\s+", "", text)
    text = re.sub(r"^본문\s+카드뉴스\s+관련법령\s+", "", text)
    text = re.sub(r"^본문\s+", "", text)
    text = strip_after_markers(text, EASYLAW_TRAILING_MARKERS)
    return clean_text(text)


def trim_easylaw_non_body_text(text: str, page_kind: str) -> str:
    text = clean_text(text)
    if page_kind == "qna":
        for marker in ["창업 :", "사업 :", "100문 100답"]:
            idx = text.find(marker)
            if idx != -1:
                text = text[idx:]
                break
        if "전체 PDF 저장" in text:
            text = text[text.find("전체 PDF 저장") + len("전체 PDF 저장") :]
        text = re.sub(r"\s*조회수:\s*\d+건\s*추천수:\s*\d+건\s*", " ", text)
        text = re.sub(r"\s*새소식 상세 내용\s*", " ", text)
        return clean_text(text)
    if page_kind == "card_news":
        for marker in ["카드뉴스", "이미지로 보는 카드뉴스"]:
            idx = text.find(marker)
            if idx != -1:
                return clean_text(text[idx:])
    if page_kind == "related_law":
        for marker in ["관련법령", "대분류"]:
            idx = text.find(marker)
            if idx != -1:
                return clean_text(text[idx:])
    return text


def easylaw_section_title(section_text: str, fallback: str) -> str:
    text = re.sub(r"^인쇄체크\s*", "", clean_text(section_text))
    if not text:
        return fallback
    sentence_end = min([pos for pos in [text.find("다."), text.find("?"), text.find("!")] if pos != -1] or [80])
    title = clean_text(text[: min(sentence_end + 2, 90)])
    words = title.split()
    if len(words) > 12:
        title = " ".join(words[:12])
    return title or fallback


def split_easylaw_sections(text: str, page_title: str, page_kind: str) -> list[tuple[str, str]]:
    text = trim_easylaw_text(text, page_title)
    if not text:
        return []
    if page_kind == "qna_list":
        return []
    if page_kind != "body":
        text = trim_easylaw_non_body_text(text, page_kind)
        return [(page_kind, text)]

    parts = [part for part in re.split(r"(?=인쇄체크\s+)", text) if clean_text(part)]
    if not parts:
        return [(page_title or "본문", text)]

    sections: list[tuple[str, str]] = []
    for idx, part in enumerate(parts):
        section_text = clean_text(part)
        if idx == 0 and "인쇄체크" not in section_text[:20]:
            if (
                "시행(개정 사항" in section_text
                and "본문" in section_text
                and len(section_text) < 180
                and "「" in section_text
            ):
                continue
            section_name = page_title or "개요"
        else:
            section_name = easylaw_section_title(section_text, page_title or "본문")
        sections.append((section_name, section_text))
    return sections


def build_easylaw_chunks(max_chars: int, overlap: int, min_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in iter_jsonl(PROCESSED / "easylaw_startup_pages.jsonl") or []:
        csm_seq = obj.get("csm_seq", "")
        business_title = clean_text(obj.get("business_title", ""))
        page_title = clean_text(obj.get("page_title", ""))
        title_parts = [part for part in [business_title, page_title] if part and part != "○"]
        title = " / ".join(title_parts) or csm_seq
        page_kind = easylaw_page_kind(obj)
        source_url = obj.get("source_url", "")
        doc_id = source_document_id("easylaw", csm_seq, page_kind, source_url[-40:])
        raw_text = extract_html_main_text(obj.get("raw_path", ""))
        source_text = raw_text or obj.get("text", "")
        for section_name, section_text in split_easylaw_sections(source_text, page_title, page_kind):
            section_path = f"{title} > {section_name}"
            for i, text in enumerate(chunk_text(section_text, max_chars=max_chars, overlap=overlap), start=1):
                add_chunk(
                    rows,
                    source_document_id=doc_id,
                    source_type="easylaw",
                    source_record_id=csm_seq,
                    authority_level="official_guide",
                    title=title,
                    section_path=section_path,
                    source_url=source_url,
                    raw_path=obj.get("raw_path", ""),
                    chunk_kind=f"{page_kind}_section",
                    sequence=i,
                    text=text,
                    min_chars=min_chars,
                )
    return rows


def flatten_law_article(article: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["조문번호", "조문제목", "조문내용"]:
        value = article.get(key)
        if value:
            parts.append(clean_text(value))

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in ["항번호", "항내용", "호번호", "호내용", "목번호", "목내용"]:
                if value.get(key):
                    parts.append(clean_text(value[key]))
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for key in ["항", "호", "목"]:
        if key in article:
            walk(article[key])
    return clean_text(" ".join(parts))


def build_law_chunks(max_chars: int, overlap: int, min_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in iter_jsonl(PROCESSED / "law_full_texts.jsonl") or []:
        law_name = clean_text(obj.get("law_name", ""))
        doc_id = source_document_id("law", law_name)
        law = obj.get("payload", {}).get("법령", {})
        articles = law.get("조문", {}).get("조문단위", [])
        if isinstance(articles, dict):
            articles = [articles]
        for article in articles:
            article_no = clean_text(article.get("조문번호", ""))
            article_title = clean_text(article.get("조문제목", ""))
            title = f"{law_name} 제{article_no}조 {article_title}".strip()
            section_path = title
            article_text = flatten_law_article(article)
            if not article_text:
                continue
            text_with_context = f"{title}\n{article_text}"
            for i, text in enumerate(chunk_text(text_with_context, max_chars=max_chars, overlap=overlap), start=1):
                add_chunk(
                    rows,
                    source_document_id=doc_id,
                    source_type="law.go.kr",
                    source_record_id=law_name,
                    authority_level="official",
                    title=title,
                    section_path=section_path,
                    source_url=obj.get("detail_url", ""),
                    raw_path=obj.get("raw_path", ""),
                    chunk_kind=f"article_{article_no}",
                    sequence=i,
                    text=text,
                    min_chars=min_chars,
                )
    return rows


def dedupe_chunks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        existing = by_id.get(row["chunk_id"])
        if existing is None or row["char_len"] > existing["char_len"]:
            by_id[row["chunk_id"]] = row
    return list(by_id.values())


def length_stats(lengths: list[int]) -> dict[str, Any]:
    if not lengths:
        return {}
    sorted_lengths = sorted(lengths)
    return {
        "min": min(lengths),
        "avg": round(mean(lengths), 1),
        "median": round(median(lengths), 1),
        "p90": sorted_lengths[int(len(sorted_lengths) * 0.9)],
        "p95": sorted_lengths[int(len(sorted_lengths) * 0.95)],
        "max": max(lengths),
    }


def write_manifest(rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    by_source = Counter(row["source_type"] for row in rows)
    by_kind = Counter(f"{row['source_type']}:{row['chunk_kind']}" for row in rows)
    by_doc = Counter(row["source_document_id"] for row in rows)
    lengths = [row["char_len"] for row in rows]

    lines = [
        "# Evidence Chunk Manifest",
        "",
        "## Parameters",
        "",
        f"- max_chars: {args.max_chars}",
        f"- overlap: {args.overlap}",
        f"- min_chars: {args.min_chars}",
        "",
        "## Totals",
        "",
        f"- total_chunks: {len(rows)}",
        f"- source_documents: {len(by_doc)}",
        f"- duplicate_chunk_ids: {len(rows) - len({row['chunk_id'] for row in rows})}",
        f"- length_stats: {length_stats(lengths)}",
        "",
        "## By Source",
        "",
    ]
    for source, count in sorted(by_source.items()):
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## By Source/Kind", ""])
    for key, count in sorted(by_kind.items()):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Notes", ""])
    lines.append("- These chunks are the canonical evidence store for graph claims and RAG embeddings.")
    lines.append("- Claim extraction can use a filtered subset of this file, but evidence grounding should point back here.")
    (OUT / "evidence_chunks_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_quality_report(rows: list[dict[str, Any]]) -> None:
    by_source = sorted(set(row["source_type"] for row in rows))
    unresolved = [row for row in rows if row["raw_path"] and not (ROOT / row["raw_path"]).exists()]
    boilerplate_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        haystack = f"{row['title']} {row['section_path']} {row['text']}"
        found = [marker for marker in BOILERPLATE_PATTERNS if marker in haystack]
        if found:
            boilerplate_hits[row["source_type"]].append(
                {
                    "chunk_id": row["chunk_id"],
                    "markers": found[:4],
                    "title": row["title"],
                }
            )

    lines = [
        "# Evidence Chunk Quality Report",
        "",
        "## Path Checks",
        "",
        f"- unresolved_raw_paths: {len(unresolved)}",
        "",
        "## Boilerplate Marker Hits",
        "",
    ]
    for source in by_source:
        hits = boilerplate_hits.get(source, [])
        lines.append(f"- {source}: {len(hits)}")
        for hit in hits[:5]:
            lines.append(f"  - {hit['chunk_id']} | {hit['markers']} | {hit['title']}")
    lines.extend(["", "## Length By Source", ""])
    for source in by_source:
        lengths = [row["char_len"] for row in rows if row["source_type"] == source]
        lines.append(f"- {source}: {length_stats(lengths)}")
    lines.extend(["", "## Lowest Relevance Samples", ""])
    for row in sorted(rows, key=lambda item: (item["relevance_score"], item["source_type"], item["char_len"]))[:20]:
        snippet = row["text"][:120].replace("\n", " ")
        lines.append(f"- score={row['relevance_score']} | {row['chunk_id']} | {row['source_type']} | {row['title']} | {snippet}")
    lines.extend(["", "## Longest Samples", ""])
    for row in sorted(rows, key=lambda item: item["char_len"], reverse=True)[:10]:
        lines.append(f"- len={row['char_len']} | {row['chunk_id']} | {row['source_type']} | {row['title']}")

    (OUT / "evidence_chunk_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare canonical evidence chunks from all local official sources.")
    parser.add_argument("--max-chars", type=int, default=1400)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    rows.extend(build_gov24_chunks(args.max_chars, args.overlap, args.min_chars))
    rows.extend(build_easylaw_chunks(args.max_chars, args.overlap, args.min_chars))
    rows.extend(build_law_chunks(args.max_chars, args.overlap, args.min_chars))
    rows = dedupe_chunks(rows)
    rows.sort(key=lambda row: (row["source_type"], row["source_document_id"], row["section_path"], row["sequence"]))
    if args.limit:
        rows = rows[: args.limit]

    write_jsonl(OUT / "evidence_chunks.jsonl", rows)
    write_manifest(rows, args)
    write_quality_report(rows)
    print(f"chunks={len(rows)} output={OUT / 'evidence_chunks.jsonl'}")


if __name__ == "__main__":
    main()
