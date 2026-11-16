from datetime import date

import pytest

from app.intake import parser_llm, stt

TODAY = date(2026, 11, 8)

@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(parser_llm, "CACHE_DIR", tmp_path / "llm")
    monkeypatch.setattr(stt, "CACHE_DIR", tmp_path / "stt")
    monkeypatch.setenv("DEMO_NOW", "2026-11-08T10:00:00")
    monkeypatch.delenv("DEMO_CLOCK", raising=False)

    def _no_network(*a, **k):
        raise parser_llm.LLMError("no_network_in_tests")

    monkeypatch.setattr(parser_llm, "PROVIDERS", {"gemini": _no_network, "claude": _no_network})

    def _no_stt(*a, **k):
        raise stt.STTError("no_network_in_tests")

    monkeypatch.setattr(stt, "BACKENDS", {"elevenlabs": _no_stt, "whisper": _no_stt})
    yield

@pytest.fixture
def today():
    return TODAY
