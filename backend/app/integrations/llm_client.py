from __future__ import annotations

import json
from http.client import IncompleteRead
import urllib.error
import urllib.request
from typing import Any

from app.core.config import Settings, settings
from app.services.output_guard import clean_payload, mask_sensitive_text


class LlmClient:
    """GMS JSON LLM client.

    The rest of the backend depends on this small boundary only. Set
    LLM_API_KEY or GMS_API_KEY to enable AI; leave them empty to use rule fallback.
    """

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def available(self) -> bool:
        return self.config.llm_available

    def generate_json(self, *, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.available:
            return None

        payload = {
            "model": self.config.llm_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(clean_payload(user_payload), ensure_ascii=False),
                },
            ],
        }
        if not self._uses_default_temperature_only():
            payload["temperature"] = 0.1
        if self.config.llm_reasoning_effort:
            payload["reasoning_effort"] = self.config.llm_reasoning_effort
        if self.config.llm_max_output_tokens:
            payload["max_completion_tokens"] = self.config.llm_max_output_tokens

        request = urllib.request.Request(
            f"{self.config.llm_base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.llm_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.llm_timeout_seconds) as response:
                body = self._read_response_body(response)
                raw = json.loads(body)
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, IncompleteRead, json.JSONDecodeError):
            return None

        content = raw.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            return None

        try:
            parsed = json.loads(mask_sensitive_text(content))
        except json.JSONDecodeError:
            return None
        return clean_payload(parsed)

    def _uses_default_temperature_only(self) -> bool:
        return self.config.llm_model.lower().startswith("gpt-5")

    @classmethod
    def _read_response_body(cls, response: Any) -> str:
        try:
            return response.read().decode("utf-8")
        except IncompleteRead as exc:
            partial = (exc.partial or b"").decode("utf-8", errors="replace")
            return cls._repair_gms_partial_json(partial)

    @staticmethod
    def _repair_gms_partial_json(text: str) -> str:
        stripped = text.lstrip()
        if stripped.startswith("{"):
            return stripped
        if stripped.startswith('"choices":'):
            return "{" + stripped
        for suffix in ("choices", "hoices", "oices", "ices", "ces", "es", "s"):
            if stripped.startswith(f'{suffix}":'):
                return '{"' + "choices"[: -len(suffix)] + stripped
        return stripped


llm_client = LlmClient()
