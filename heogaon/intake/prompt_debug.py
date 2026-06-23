from __future__ import annotations

import json
from typing import Any

from ai_judgement import build_ai_judgement_prompt
from inquiry_package import build_llm_script_prompt
from slot_contract import build_slot_filler_prompt


PREVIEW_LIMIT = 6000
DEBUG_VERSION = "prompt-debug-v2"


def approx_tokens(text: str) -> int:
    # Korean prompts vary a lot by tokenizer. This is a rough UI-only estimate.
    return max(1, round(len(text) / 2.2))


def prompt_text(prompt: dict[str, Any]) -> tuple[str, str]:
    system = str(prompt.get("system") or "")
    user = json.dumps(prompt.get("user", {}), ensure_ascii=False, separators=(",", ":"))
    return system, user


def provider_sent_to_ai(meta: dict[str, Any]) -> bool:
    return str(meta.get("requestedProvider") or meta.get("provider") or "").lower() in {"gms", "openai"}


def make_prompt_stat(name: str, prompt: dict[str, Any], reason: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    system, user = prompt_text(prompt)
    combined = system + "\n" + user
    preview = combined[:PREVIEW_LIMIT]
    user_payload = prompt.get("user") if isinstance(prompt.get("user"), dict) else {}
    field_chars = {
        key: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        for key, value in user_payload.items()
    }
    meta = meta or {}
    sent_to_ai = provider_sent_to_ai(meta)
    return {
        "name": name,
        "reason": reason,
        "provider": meta.get("provider") or meta.get("requestedProvider") or "unknown",
        "requestedProvider": meta.get("requestedProvider") or meta.get("provider") or "unknown",
        "fallbackUsed": bool(meta.get("fallbackUsed")),
        "sentToAi": sent_to_ai,
        "systemChars": len(system),
        "userChars": len(user),
        "totalChars": len(combined),
        "estimatedTokens": approx_tokens(combined),
        "truncated": len(combined) > PREVIEW_LIMIT,
        "preview": preview,
        "userTopLevelKeys": list(user_payload.keys()),
        "userFieldChars": field_chars,
    }


def build_prompt_debug(result: dict[str, Any]) -> dict[str, Any]:
    inquiry = result.get("inquiryPackage") or {}
    contacts = inquiry.get("contacts") or []
    check_items = inquiry.get("checkItems") or []
    slot_meta = (result.get("slotFilling") or {}).get("meta", {})
    judgement_meta = (result.get("aiJudgement") or {}).get("meta", {})
    inquiry_meta = ((inquiry.get("scripts") or {}).get("meta") or {})
    prompts = [
        make_prompt_stat(
            "slot_filling",
            build_slot_filler_prompt(str(result.get("inputText") or "")),
            "Natural language -> intent, address, business type candidates, area, liquor, signboard/outdoor slots.",
            slot_meta,
        ),
        make_prompt_stat(
            "ai_judgement",
            (result.get("aiJudgement") or {}).get("prompt") or build_ai_judgement_prompt(result),
            "Slots + API/decision status + graph summary -> final guidance state and questions.",
            judgement_meta,
        ),
        make_prompt_stat(
            "inquiry_script",
            build_llm_script_prompt(result, contacts, check_items),
            "Contacts + checklist + document/order summary -> phone/online inquiry script.",
            inquiry_meta,
        ),
    ]
    actual_prompts = [item for item in prompts if item["sentToAi"]]
    return {
        "version": DEBUG_VERSION,
        "moduleFile": __file__,
        "note": "Token counts are local estimates for the prompt input only. Actual billing/usage depends on the GMS tokenizer, reasoning tokens, and output size.",
        "callCount": len(prompts),
        "actualAiCallCount": len(actual_prompts),
        "totalEstimatedInputTokens": sum(item["estimatedTokens"] for item in prompts),
        "actualEstimatedInputTokens": sum(item["estimatedTokens"] for item in actual_prompts),
        "totalChars": sum(item["totalChars"] for item in prompts),
        "actualChars": sum(item["totalChars"] for item in actual_prompts),
        "calls": prompts,
    }
