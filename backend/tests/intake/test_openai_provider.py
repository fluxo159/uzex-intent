import json

import httpx
import pytest

from app.intake import parser_llm as pl
from app.intake import stt

class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload

    def json(self):
        return self._p

def test_order_prefers_providers_with_keys(monkeypatch):
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert pl._effective_order() == pl.ORDER
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert pl._effective_order()[0] == "openai"
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert pl._effective_order()[:2] == ("openai", "gemini")

def test_call_openai_parses_json_schema_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = json
        captured["auth"] = headers.get("Authorization")
        return _Resp(200, {"choices": [{"message": {"content": '{"qty_value": 200, "region": "Namangan"}'}}]})

    monkeypatch.setattr(pl.httpx, "post", fake_post)
    raw = pl.call_openai("200 тонн цемента м400 наманган", 5.0)
    assert raw["qty_value"] == 200 and raw["region"] == "Namangan"
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["temperature"] == 0

def test_call_openai_no_key_and_http_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(pl.LLMError, match="no_key"):
        pl.call_openai("x", 1.0)
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    monkeypatch.setattr(pl.httpx, "post", lambda *a, **k: _Resp(429, {}))
    with pytest.raises(pl.LLMError, match="http_429"):
        pl.call_openai("x", 1.0)

def test_openai_transcribe_maps_language(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    monkeypatch.setattr(stt, "OPENAI_STT_MODEL", "whisper-1")

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        assert url.endswith("/v1/audio/transcriptions") and data["language"] == "uz"
        return _Resp(200, {"text": " Namanganga 200 tonna ", "language": "uzbek"})

    monkeypatch.setattr(stt.httpx, "post", fake_post)
    res = stt.openai_transcribe(b"abc", "uz")
    assert res == {"transcript": "Namanganga 200 tonna", "lang": "uz", "source": "openai"}

def test_stt_order_has_openai_first_online(monkeypatch):
    monkeypatch.setattr(stt, "offline", lambda: False)
    calls = []

    def fake(name):
        def fn(*a, **k):
            calls.append(name)
            raise stt.STTError("no_key")
        return fn

    monkeypatch.setattr(stt, "BACKENDS", {"openai": fake("openai"), "elevenlabs": fake("elevenlabs"), "whisper": fake("whisper")})
    monkeypatch.setattr(stt, "_cache_get", lambda h, l: None)
    stt.transcribe(b"audio-bytes", "ru")
    assert calls[:2] == ["openai", "elevenlabs"]

def test_openai_transcribe_gpt_transcribe_uses_json_and_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    monkeypatch.setattr(stt, "OPENAI_STT_MODEL", "gpt-transcribe")

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        assert data["response_format"] == "json" and "language" not in data and "tsement" in data["prompt"]
        return _Resp(200, {"text": "Namanganga 200 tonna"})

    monkeypatch.setattr(stt.httpx, "post", fake_post)
    assert stt.openai_transcribe(b"abc", "uz") == {"transcript": "Namanganga 200 tonna", "lang": "uz", "source": "openai"}

def test_call_openai_falls_back_on_400(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    models = []

    def fake_post(url, json=None, headers=None, timeout=None):
        models.append(json["model"])
        if len(models) == 1:
            return _Resp(400, {"error": "unsupported"})
        return _Resp(200, {"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(pl.httpx, "post", fake_post)
    assert pl.call_openai("x", 5.0) == {}
    assert models == [pl.OPENAI_MODEL, pl.OPENAI_MODEL_FALLBACK]
