import json

import httpx
import pytest

from otasec import llm


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


def test_request_shape_and_parse(monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, json=json, headers=headers)
        return Resp(200, {"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"ok": true}'}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = llm.complete_json("k", "claude-haiku-5-5", "sys", "user", {"type": "object"})
    assert out == {"ok": True}
    assert seen["json"]["output_config"]["format"]["type"] == "json_schema"
    assert seen["headers"]["x-api-key"] == "k" and "anthropic-version" in seen["headers"]


def test_retries_then_fails_fast_on_400(monkeypatch):
    calls = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    def overloaded(*a, **k):
        calls.append(1)
        return Resp(529, {"error": "overloaded"}) if len(calls) < 3 else \
            Resp(200, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]})

    monkeypatch.setattr(httpx, "post", overloaded)
    assert llm.complete_json("k", "m", "s", "u", {}) == {}
    assert len(calls) == 3

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Resp(400, {"error": "bad model"}))
    with pytest.raises(llm.LLMError):
        llm.complete_json("k", "m", "s", "u", {})
