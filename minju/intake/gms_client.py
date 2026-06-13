from __future__ import annotations

import json
import os
import http.client
import urllib.error
import urllib.request
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_GMS_BASE_URL = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"
DEFAULT_GMS_MODEL = "gpt-5.5"


class GMSProviderUnavailable(RuntimeError):
    pass


def normalize_model_name(model: str | None) -> str:
    value = (model or DEFAULT_GMS_MODEL).strip()
    compact = value.lower().replace("_", "-").replace(" ", "")
    aliases = {
        "gpt5": "gpt-5",
        "gpt-5": "gpt-5",
        "gpt41": "gpt-4.1",
        "gpt4.1": "gpt-4.1",
        "gpt-4.1": "gpt-4.1",
        "gpt55": "gpt-5.5",
        "gpt5.5": "gpt-5.5",
        "gpt-5.5": "gpt-5.5",
        "gpt5nano": "gpt-5-nano",
        "gpt-5nano": "gpt-5-nano",
        "gpt-5-nano": "gpt-5-nano",
    }
    return aliases.get(compact, value)


def gms_config() -> dict[str, Any]:
    api_key = os.getenv("HEOGAON_GMS_API_KEY") or os.getenv("GMS_API_KEY") or ""
    model = normalize_model_name(os.getenv("HEOGAON_GMS_MODEL") or os.getenv("GMS_MODEL") or os.getenv("HEOGAON_AI_MODEL"))
    base_url = os.getenv("HEOGAON_GMS_BASE_URL") or os.getenv("GMS_BASE_URL") or DEFAULT_GMS_BASE_URL
    max_output_tokens = int(os.getenv("GMS_MAX_OUTPUT_TOKENS") or os.getenv("HEOGAON_GMS_MAX_OUTPUT_TOKENS") or "6000")
    reasoning_effort = os.getenv("GMS_REASONING_EFFORT") or os.getenv("HEOGAON_GMS_REASONING_EFFORT") or "low"
    return {
        "apiKey": api_key,
        "model": model,
        "baseUrl": base_url.rstrip("/"),
        "maxOutputTokens": max_output_tokens,
        "reasoningEffort": reasoning_effort,
    }


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def extract_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def build_chat_payload(
    *,
    model: str,
    system_prompt: str,
    user_payload: Any,
    temperature: float,
    max_output_tokens: int,
    reasoning_effort: str,
    json_mode: bool,
) -> dict[str, Any]:
    instruction_role = "developer" if model.startswith(("gpt-5", "o3", "o4")) else "system"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": instruction_role, "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False) if not isinstance(user_payload, str) else user_payload},
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
    return payload


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


def request_chat_completion(config: dict[str, Any], payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not config["apiKey"]:
        raise GMSProviderUnavailable("GMS_API_KEY is not set.")
    url = config["baseUrl"] + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['apiKey']}",
        "Content-Type": "application/json",
    }
    if "gms.ssafy.io" in url:
        return request_json_with_curl(url, payload, headers, timeout)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept-Encoding": "identity",
            "Connection": "close",
            **headers,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            try:
                data = response.read()
            except http.client.IncompleteRead as exc:
                data = exc.partial
            return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"GMS HTTP {exc.code}: {message}") from exc


def gms_chat_json(
    *,
    system_prompt: str,
    user_payload: Any,
    temperature: float = 0.1,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    config = gms_config()
    payload = build_chat_payload(
        model=config["model"],
        system_prompt=system_prompt,
        user_payload=user_payload,
        temperature=temperature,
        max_output_tokens=max_output_tokens or config["maxOutputTokens"],
        reasoning_effort=config["reasoningEffort"] if reasoning_effort is None else reasoning_effort,
        json_mode=True,
    )
    raw = request_chat_completion(config, payload, timeout)
    content = extract_chat_text(raw)
    parsed = parse_json_object(content)
    if isinstance(parsed, dict):
        parsed.setdefault("_gmsMeta", {"model": config["model"], "baseUrl": config["baseUrl"], "usage": raw.get("usage", {})})
    return parsed
