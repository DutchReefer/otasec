"""Minimal Claude Messages API client with JSON structured outputs.

Uses `output_config.format = {type: json_schema}` (GA, no beta header), so the
reply is guaranteed to parse against the schema. Raw httpx keeps dependencies
small; retries cover 429/5xx/overloaded.
"""
from __future__ import annotations

import json
import logging
import time

import httpx

log = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class LLMError(RuntimeError):
    pass


def complete_json(api_key: str, model: str, system: str, user: str, schema: dict,
                  max_tokens: int = 8000, retries: int = 4, timeout: float = 180) -> dict:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }
    delay = 5.0
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.post(API_URL, json=payload, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            last_err = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stop_reason") == "refusal":
                    raise LLMError("request refused")
                if data.get("stop_reason") == "max_tokens":
                    raise LLMError("response truncated (max_tokens)")
                text = next((b["text"] for b in data.get("content", []) if b.get("type") == "text"), "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"invalid JSON from model: {exc}") from exc
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in (408, 429, 500, 502, 503, 504, 529):
                raise LLMError(last_err)
        if attempt < retries:
            log.warning("Claude API attempt %d failed (%s); retrying in %.0fs", attempt, last_err, delay)
            time.sleep(delay)
            delay *= 2
    raise LLMError(last_err)
