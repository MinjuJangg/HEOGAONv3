from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


GRAPH_ROOT = Path(__file__).resolve().parents[1]
ROOT = GRAPH_ROOT
OUT = GRAPH_ROOT / "output" / "intermediate"
DEFAULT_QUEUE = OUT / "claim_extraction_queue.jsonl"
DEFAULT_RAW = OUT / "llm_claims_raw.jsonl"
DEFAULT_CLAIMS = OUT / "llm_claims.jsonl"
DEFAULT_CACHE_DIR = OUT / "llm_cache"
DEFAULT_DRY_RUN = OUT / "llm_claim_extraction_dry_run.md"

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-5-nano"

NODE_TYPES = {
    "business_alias",
    "admin_business_type",
    "condition_module",
    "permit_service",
    "document",
    "check_item",
    "department_function",
    "legal_basis",
    "procedure_step",
    "risk_flag",
    "source_document",
    "evidence_chunk",
}

ALLOWED_PAIRS = {
    "maps_to": {("business_alias", "admin_business_type")},
    "requires_permit": {("admin_business_type", "permit_service")},
    "triggers": {
        ("condition_module", "permit_service"),
        ("condition_module", "check_item"),
        ("condition_module", "document"),
        ("condition_module", "admin_business_type"),
        ("condition_module", "risk_flag"),
    },
    "requires_document": {
        ("permit_service", "document"),
        ("admin_business_type", "document"),
    },
    "needs_check": {
        ("permit_service", "check_item"),
        ("condition_module", "check_item"),
        ("admin_business_type", "check_item"),
    },
    "handled_by": {
        ("permit_service", "department_function"),
        ("check_item", "department_function"),
    },
    "requires_prerequisite": {
        ("document", "document"),
        ("document", "check_item"),
        ("document", "procedure_step"),
        ("permit_service", "document"),
        ("permit_service", "check_item"),
        ("permit_service", "procedure_step"),
        ("procedure_step", "document"),
        ("procedure_step", "check_item"),
        ("procedure_step", "procedure_step"),
    },
    "based_on": {
        ("permit_service", "legal_basis"),
        ("document", "legal_basis"),
        ("check_item", "legal_basis"),
        ("condition_module", "legal_basis"),
        ("admin_business_type", "legal_basis"),
    },
    "precedes": {("procedure_step", "procedure_step")},
    "raises_risk": {
        ("condition_module", "risk_flag"),
        ("admin_business_type", "risk_flag"),
        ("permit_service", "risk_flag"),
    },
    "has_source": {
        ("permit_service", "source_document"),
        ("admin_business_type", "source_document"),
        ("condition_module", "source_document"),
        ("document", "source_document"),
        ("check_item", "source_document"),
        ("legal_basis", "source_document"),
    },
    "supported_by": {("source_document", "evidence_chunk")},
}

SYSTEM_PROMPT = """You are an evidence-grounded GraphRAG claim extractor.
Extract only claims explicitly stated in the provided Korean official/legal chunk.
Return JSON only. Do not summarize, infer, or add outside knowledge."""

USER_PROMPT_TEMPLATE = """Read the source chunk and extract graph claims for a permit-decision GraphRAG.

Allowed node types:
- business_alias
- admin_business_type
- condition_module
- permit_service
- document
- check_item
- department_function
- legal_basis
- procedure_step
- risk_flag
- source_document
- evidence_chunk

Allowed predicates and type pairs:
- maps_to: business_alias -> admin_business_type
- requires_permit: admin_business_type -> permit_service
- triggers: condition_module -> permit_service/check_item/document/admin_business_type/risk_flag
- requires_document: permit_service/admin_business_type -> document
- needs_check: permit_service/condition_module/admin_business_type -> check_item
- handled_by: permit_service/check_item -> department_function
- requires_prerequisite: document/permit_service/procedure_step -> document/check_item/procedure_step
- based_on: permit_service/document/check_item/condition_module/admin_business_type -> legal_basis
- precedes: procedure_step -> procedure_step
- raises_risk: condition_module/admin_business_type/permit_service -> risk_flag

Extraction rules:
1. Extract only claims directly supported by the chunk text.
2. evidence_text must be a short exact excerpt copied from the chunk.
3. Use concise Korean node names.
4. Do not invent local office names. Use department functions such as "식품위생 업무", "건축물 용도 업무", "옥외광고물 관리 업무".
5. If a condition is optional, exceptional, or requires official confirmation, represent it as check_item or risk_flag, not as a certain requirement.
6. Prefer high-value permit/document/check/legal-basis claims over generic definitions.
7. Output at most {max_claims} claims. If fewer than {max_claims} claims are clearly supported, output fewer.
8. When using a weaker model, be conservative: a small set of exact, high-confidence claims is better than many broad claims.

Important modeling rules:
- If the chunk lists submitted documents, use:
  permit_service "{title}" -> requires_document -> document "document name".
  Put parenthetical applicability conditions into condition_text.
- If the chunk lists documents checked by officials, use:
  permit_service "{title}" -> needs_check -> check_item "checked item".
- If the chunk lists legal bases, use:
  permit_service "{title}" -> based_on -> legal_basis "law/article".
- Do not use a document name, legal article, or condition phrase as object_type=permit_service.
- Do not use triggers unless the subject is truly a user/business condition such as "간판 설치", "주류 판매", "지하수 사용", "도로 점용".
- Predicate triggers must always have subject_type=condition_module. Never output permit_service -> triggers -> condition_module.
- Never output permit_service -> triggers -> anything. If a condition causes a permit/check/document/risk, make the condition the subject.
- Never invent predicate names. Forbidden examples: "required_document", "handles", "has_requirement", "requires_check".
- Never invent node types. Forbidden examples: "administration", "agency", "office", "fee", "period".
- Avoid handled_by and precedes unless the chunk explicitly states an administrative function or an ordered procedure. Otherwise omit them.
- Do not use generic section titles as node names: "본문", "관련법령", "서비스 개요", "기본정보", numeric titles such as "839" or "840".
- For EasyLaw/law.go.kr chunks, do not force the source title into subject_name. Use a concrete node from the text such as "휴게음식점영업", "일반음식점영업", "식품관련영업신고", "옥외광고물 표시허가", "도로점용허가".
- Do not output has_source or supported_by claims. The pipeline attaches source_document_id and chunk_id automatically.
- Do not extract generic UI/admin phrases such as "구비서류 있음", "처리기간", "수수료 없음", or "하단 참조" unless they are necessary permit attributes.
- For "담당공무원이 확인" sections, use permit_service -> needs_check -> check_item and make each checked item a concrete official-check item.
- Copy evidence_text exactly as one continuous substring from the chunk, including punctuation when possible. Do not paraphrase evidence_text.
- If the exact supporting text is long, copy a shorter continuous substring that still contains the subject/object relation.

Return exactly this JSON shape:
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
      "condition_text": "식품위생법 제41조제2항에 따라 미리 교육을 받은 경우만 해당",
      "evidence_text": "exact excerpt from the chunk"
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

Chunk:
{chunk_text}
"""


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def stable_id(prefix: str, *parts: str) -> str:
    raw = "||".join(clean_text(part) for part in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def request_json_with_curl(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required for the GMS proxy fallback but was not found.")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        command = [
            curl,
            "-sS",
            "--max-time",
            str(timeout),
            "-w",
            "\n__HTTP_STATUS__:%{http_code}",
            url,
        ]
        for key, value in headers.items():
            command.extend(["-H", f"{key}: {value}"])
        command.extend(["--data-binary", f"@{tmp_path}"])
        result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    output = result.stdout or ""
    body, marker, status = output.rpartition("\n__HTTP_STATUS__:")
    if not marker:
        raise RuntimeError(f"curl request failed: {(result.stderr or output)[:1000]}")
    try:
        status_code = int(status.strip() or "0")
    except ValueError as exc:
        raise RuntimeError(f"curl request returned an invalid status marker: {status[:100]}") from exc
    if status_code >= 400:
        raise RuntimeError(f"HTTP {status_code}: {body[:1000]}")
    if result.returncode != 0:
        raise RuntimeError(f"curl request failed: {(result.stderr or body)[:1000]}")
    return json.loads(body)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_default_env_files(extra_paths: list[Path]) -> None:
    for path in [ROOT / ".env.gms", *extra_paths]:
        load_env_file(path)


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 2.2))


def prepare_prompt(chunk: dict[str, Any], max_claims: int) -> str:
    return USER_PROMPT_TEMPLATE.format(
        max_claims=max_claims,
        authority_level=chunk.get("authority_level", "official"),
        chunk_id=chunk.get("chunk_id", ""),
        source_document_id=chunk.get("source_document_id", ""),
        source_type=chunk.get("source_type", ""),
        title=chunk.get("title", ""),
        section_path=chunk.get("section_path", ""),
        chunk_text=chunk.get("text", ""),
    )


def parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def request_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    if "gms.ssafy.io" in url:
        return request_json_with_curl(url, payload, headers, timeout)
    headers = {
        "Accept-Encoding": "identity",
        "Connection": "close",
        **headers,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            try:
                body = response.read()
            except http.client.IncompleteRead as exc:
                body = exc.partial
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            raw_body = exc.read()
        except http.client.IncompleteRead as read_exc:
            raw_body = read_exc.partial
        body = raw_body.decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:1000]}") from exc


def call_gemini(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_output_tokens: int,
    timeout: int,
) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        },
    }
    return request_json(url, payload, {"Content-Type": "application/json"}, timeout)


def extract_gemini_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))


def call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_output_tokens: int,
    reasoning_effort: str,
    timeout: int,
    json_mode: bool,
) -> dict[str, Any]:
    instruction_role = "developer" if model.startswith(("gpt-5", "o3", "o4")) else "system"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": instruction_role, "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if model.startswith(("gpt-5", "o3", "o4")):
        payload["max_completion_tokens"] = max_output_tokens
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
    else:
        payload["max_tokens"] = max_output_tokens
        payload["temperature"] = temperature
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return request_json(
        base_url.rstrip("/") + "/chat/completions",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout,
    )


def extract_openai_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def choose_provider(requested: str) -> str:
    if requested != "auto":
        return requested
    if os.getenv("GMS_BASE_URL") or os.getenv("OPENAI_BASE_URL"):
        return "openai"
    key = os.getenv("GMS_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if key.startswith("sk-"):
        return "openai"
    return "gemini"


def provider_config(provider: str) -> tuple[str, str, str]:
    if provider == "gemini":
        api_key = os.getenv("GMS_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        model = os.getenv("GMS_MODEL") or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        return api_key, model, ""
    api_key = os.getenv("GMS_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    model = os.getenv("GMS_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    base_url = os.getenv("GMS_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    return api_key, model, base_url


def normalized_contains(haystack: str, needle: str) -> bool:
    haystack = clean_text(haystack)
    needle = clean_text(needle)
    return bool(needle) and needle in haystack


LOW_VALUE_NODE_NAMES = {
    "본문",
    "관련법령",
    "서비스 개요",
    "기본정보",
    "처리기간",
    "수수료",
    "구비서류",
    "하단 참조",
    "해당 없음",
    "민원인이 제출해야하는 서류",
    "민원인이 제출하지 않아도 되는 서류",
}


def is_low_value_node_name(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return False
    return text in LOW_VALUE_NODE_NAMES or bool(re.fullmatch(r"\d+", text))


def normalize_raw_claim(claim: dict[str, Any]) -> dict[str, Any]:
    row = dict(claim)
    subject_type = clean_text(row.get("subject_type", ""))
    object_type = clean_text(row.get("object_type", ""))
    predicate = clean_text(row.get("predicate", ""))

    predicate_aliases = {
        "required_document": "requires_document",
        "requires_documents": "requires_document",
        "need_check": "needs_check",
        "requires_check": "needs_check",
    }
    if predicate in predicate_aliases:
        row["predicate"] = predicate_aliases[predicate]
        predicate = row["predicate"]

    if predicate == "triggers" and subject_type != "condition_module":
        if object_type == "condition_module":
            row["subject_type"], row["object_type"] = row["object_type"], row["subject_type"]
            row["subject_name"], row["object_name"] = row.get("object_name", ""), row.get("subject_name", "")
        elif object_type == "risk_flag":
            row["predicate"] = "raises_risk"
        elif object_type == "check_item":
            row["predicate"] = "needs_check"

    if predicate == "requires_permit" and subject_type == "permit_service" and object_type == "admin_business_type":
        row["subject_type"], row["object_type"] = row["object_type"], row["subject_type"]
        row["subject_name"], row["object_name"] = row.get("object_name", ""), row.get("subject_name", "")

    return row


def validate_claim(claim: dict[str, Any], chunk: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["subject_type", "subject_name", "predicate", "object_type", "object_name", "evidence_text"]
    for field in required:
        if not clean_text(claim.get(field, "")):
            errors.append(f"missing_{field}")

    subject_type = clean_text(claim.get("subject_type", ""))
    object_type = clean_text(claim.get("object_type", ""))
    predicate = clean_text(claim.get("predicate", ""))
    if subject_type and subject_type not in NODE_TYPES:
        errors.append("invalid_subject_type")
    if object_type and object_type not in NODE_TYPES:
        errors.append("invalid_object_type")
    if predicate not in ALLOWED_PAIRS:
        errors.append("invalid_predicate")
    elif (subject_type, object_type) not in ALLOWED_PAIRS[predicate]:
        errors.append("invalid_type_pair")

    if subject_type in NODE_TYPES and subject_type not in {"source_document", "evidence_chunk"}:
        if is_low_value_node_name(claim.get("subject_name", "")):
            errors.append("low_value_subject_name")
    if object_type in NODE_TYPES and object_type not in {"source_document", "evidence_chunk"}:
        if is_low_value_node_name(claim.get("object_name", "")):
            errors.append("low_value_object_name")

    evidence_text = clean_text(claim.get("evidence_text", ""))
    if evidence_text and not normalized_contains(chunk.get("text", ""), evidence_text):
        errors.append("evidence_not_substring")
    return errors


def enrich_claim(claim: dict[str, Any], chunk: dict[str, Any], model: str) -> dict[str, Any]:
    row = {
        "subject_type": clean_text(claim.get("subject_type", "")),
        "subject_name": clean_text(claim.get("subject_name", "")),
        "predicate": clean_text(claim.get("predicate", "")),
        "object_type": clean_text(claim.get("object_type", "")),
        "object_name": clean_text(claim.get("object_name", "")),
        "assertion_level": clean_text(claim.get("assertion_level", "explicit")) or "explicit",
        "authority_level": clean_text(claim.get("authority_level", chunk.get("authority_level", "official"))),
        "review_status": clean_text(claim.get("review_status", "official_document")) or "official_document",
        "confidence": claim.get("confidence", 0.8),
        "condition_text": clean_text(claim.get("condition_text", "")),
        "evidence_text": clean_text(claim.get("evidence_text", "")),
        "source_document_id": chunk.get("source_document_id", ""),
        "chunk_id": chunk.get("chunk_id", ""),
        "source_type": chunk.get("source_type", ""),
        "source_record_id": chunk.get("source_record_id", ""),
        "source_url": chunk.get("source_url", ""),
        "raw_path": chunk.get("raw_path", ""),
        "title": chunk.get("title", ""),
        "section_path": chunk.get("section_path", ""),
        "extraction_method": "llm",
        "model": model,
    }
    row["validation_errors"] = validate_claim(row, chunk)
    if row["validation_errors"] and row["review_status"] == "official_document":
        row["review_status"] = "needs_review"
    row["claim_id"] = stable_id(
        "claim",
        row["chunk_id"],
        row["subject_type"],
        row["subject_name"],
        row["predicate"],
        row["object_type"],
        row["object_name"],
        row["evidence_text"],
    )
    return row


def load_done_chunk_ids(raw_path: Path, cache_dir: Path) -> set[str]:
    done: set[str] = set()
    if raw_path.exists():
        for row in iter_jsonl(raw_path):
            chunk_id = row.get("chunk_id")
            if chunk_id:
                done.add(chunk_id)
    if cache_dir.exists():
        for path in cache_dir.glob("*.json"):
            done.add(path.stem)
    return done


def dry_run_report(chunks: list[dict[str, Any]], max_claims: int, max_output_tokens: int) -> str:
    prompt_tokens = sum(estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(prepare_prompt(c, max_claims)) for c in chunks)
    output_ceiling = len(chunks) * max_output_tokens
    by_source: dict[str, int] = {}
    for chunk in chunks:
        by_source[chunk.get("source_type", "")] = by_source.get(chunk.get("source_type", ""), 0) + 1
    lines = [
        "# LLM Claim Extraction Dry Run",
        "",
        f"- chunks_to_process: {len(chunks)}",
        f"- estimated_prompt_tokens: {prompt_tokens:,}",
        f"- reserved_output_tokens: {output_ceiling:,}",
        f"- rough_total_token_ceiling: {prompt_tokens + output_ceiling:,}",
        "",
        "## By Source",
        "",
    ]
    for key, value in sorted(by_source.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## First 20", ""])
    for chunk in chunks[:20]:
        lines.append(
            f"- {chunk.get('queue_id', '')} | {chunk.get('source_type')} | "
            f"score={chunk.get('relevance_score')} | {chunk.get('title')} | {chunk.get('chunk_id')}"
        )
    return "\n".join(lines) + "\n"


def call_model(args: argparse.Namespace, provider: str, api_key: str, model: str, base_url: str, prompt: str) -> tuple[str, dict[str, Any]]:
    if provider == "gemini":
        response = call_gemini(
            api_key=api_key,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout=args.timeout,
        )
        return extract_gemini_text(response), response
    response = call_openai_compatible(
        base_url=base_url,
        api_key=api_key,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        reasoning_effort=args.reasoning_effort,
        timeout=args.timeout,
        json_mode=args.json_mode,
    )
    return extract_openai_text(response), response


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM claim extraction over the prepared evidence queue.")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--claims-output", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--env-file", type=Path, action="append", default=[])
    parser.add_argument("--provider", choices=["auto", "gemini", "openai"], default="auto")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--max-claims", type=int, default=10)
    parser.add_argument("--max-output-tokens", type=int, default=int(os.getenv("GMS_MAX_OUTPUT_TOKENS", "4000")))
    parser.add_argument("--reasoning-effort", default=os.getenv("GMS_REASONING_EFFORT", "minimal"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--retry", type=int, default=3)
    parser.add_argument("--skip-done", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--json-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_default_env_files(args.env_file)

    if not args.queue.exists():
        raise SystemExit(f"Missing queue file: {args.queue}. Run prepare_claim_extraction_queue.py first.")

    queue = list(iter_jsonl(args.queue))
    if args.start:
        queue = queue[args.start :]

    done = load_done_chunk_ids(args.raw_output, args.cache_dir)
    if args.skip_done:
        queue = [chunk for chunk in queue if chunk.get("chunk_id") not in done]
    if args.limit:
        queue = queue[: args.limit]

    report = dry_run_report(queue, args.max_claims, args.max_output_tokens)
    DEFAULT_DRY_RUN.write_text(report, encoding="utf-8")
    print(report)
    if args.dry_run:
        return

    provider = choose_provider(args.provider)
    api_key, model, base_url = provider_config(provider)
    if not api_key:
        raise SystemExit("Missing API key. Put GMS_API_KEY=... in minju/graph/.env.gms or set GEMINI_API_KEY/OPENAI_API_KEY.")

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    for idx, chunk in enumerate(queue, start=1):
        chunk_id = chunk["chunk_id"]
        cache_path = args.cache_dir / f"{chunk_id}.json"
        prompt = prepare_prompt(chunk, args.max_claims)
        last_error = ""
        for attempt in range(1, args.retry + 1):
            try:
                content, raw_response = call_model(args, provider, api_key, model, base_url, prompt)
                parsed = parse_json_object(content)
                raw_claims = parsed.get("claims") or []
                if not isinstance(raw_claims, list):
                    raw_claims = []
                claims = [
                    enrich_claim(normalize_raw_claim(claim), chunk, model)
                    for claim in raw_claims
                    if isinstance(claim, dict)
                ]
                raw_row = {
                    "chunk_id": chunk_id,
                    "queue_id": chunk.get("queue_id", ""),
                    "source_document_id": chunk.get("source_document_id", ""),
                    "source_type": chunk.get("source_type", ""),
                    "source_record_id": chunk.get("source_record_id", ""),
                    "authority_level": chunk.get("authority_level", ""),
                    "title": chunk.get("title", ""),
                    "section_path": chunk.get("section_path", ""),
                    "source_url": chunk.get("source_url", ""),
                    "raw_path": chunk.get("raw_path", ""),
                    "chunk_kind": chunk.get("chunk_kind", ""),
                    "chunk_sequence": chunk.get("sequence", ""),
                    "chunk_relevance_score": chunk.get("relevance_score", ""),
                    "scope_tags": chunk.get("scope_tags", []),
                    "provider": provider,
                    "model": model,
                    "claims_count": len(claims),
                    "raw_claims": raw_claims,
                    "raw_response": raw_response,
                }
                write_json(cache_path, raw_row)
                append_jsonl(args.raw_output, [raw_row])
                if claims:
                    append_jsonl(args.claims_output, claims)
                invalid_count = sum(1 for claim in claims if claim["validation_errors"])
                print(f"[{idx}/{len(queue)}] {chunk_id} claims={len(claims)} invalid={invalid_count}")
                break
            except Exception as exc:  # noqa: BLE001 - keep batch extraction moving.
                last_error = repr(exc)
                wait = min(12.0, args.sleep * (2**attempt))
                print(f"[retry {attempt}/{args.retry}] {chunk_id}: {last_error}; sleep={wait}")
                time.sleep(wait)
        else:
            error_row = {
                "chunk_id": chunk_id,
                "queue_id": chunk.get("queue_id", ""),
                "source_document_id": chunk.get("source_document_id", ""),
                "source_type": chunk.get("source_type", ""),
                "title": chunk.get("title", ""),
                "provider": provider,
                "model": model,
                "claims_count": 0,
                "error": last_error,
            }
            write_json(cache_path, error_row)
            append_jsonl(args.raw_output, [error_row])
            print(f"[failed] {chunk_id}: {last_error}")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
