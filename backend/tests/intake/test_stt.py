from app.intake import stt

def test_empty_audio():
    r = stt.transcribe(b"")
    assert r["error"] == "empty_audio" and r["transcript"] == ""

def test_nothing_available_is_clean_error():
    r = stt.transcribe(b"\x00\x01fake-audio")
    assert r["error"] == "stt_unavailable" and r["source"] == "none"

def test_online_then_cache(monkeypatch):
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    calls = []

    def eleven(audio, lang, filename):
        calls.append(lang)
        return {"transcript": "Qarshiga 100 tonna sement", "lang": "uz", "source": "elevenlabs"}

    monkeypatch.setitem(stt.BACKENDS, "elevenlabs", eleven)
    a = stt.transcribe(b"abc", "uz")
    b = stt.transcribe(b"abc", "uz")
    assert a["source"] == "elevenlabs" and b["cached"] and len(calls) == 1

def test_offline_uses_whisper_only(monkeypatch):
    monkeypatch.setenv("DEMO_OFFLINE", "1")

    def eleven(*a):
        raise AssertionError("no network offline")

    monkeypatch.setitem(stt.BACKENDS, "elevenlabs", eleven)
    monkeypatch.setitem(stt.BACKENDS, "whisper", lambda audio, lang: {"transcript": "200 тонн", "lang": "ru", "source": "whisper"})
    assert stt.transcribe(b"xyz")["source"] == "whisper"

def test_fallback_to_whisper(monkeypatch):
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    monkeypatch.setitem(stt.BACKENDS, "whisper", lambda audio, lang: {"transcript": "x", "lang": "uz", "source": "whisper"})
    assert stt.transcribe(b"q")["source"] == "whisper"

def test_turkic_mapping():
    for code in ("kk", "tr", "tk", "az", "ky"):
        assert stt.map_lang(code) == "uz"
    assert stt.map_lang("ru") == "ru" and stt.map_lang("uzb") == "uz" and stt.map_lang("rus") == "ru"

def test_whisper_defaults(monkeypatch):
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    assert stt.whisper_config(cuda=True) == {"model": "medium", "device": "cuda", "compute_type": "int8_float16"}
    assert stt.whisper_config(cuda=False) == {"model": "small", "device": "cpu", "compute_type": "int8"}
    monkeypatch.setenv("WHISPER_MODEL", "large-v3")
    assert stt.whisper_config(cuda=True)["model"] == "large-v3"

def test_reason_code(monkeypatch):
    def missing(audio, lang):
        raise stt.STTError("whisper_model_missing")

    monkeypatch.setitem(stt.BACKENDS, "whisper", missing)
    r = stt.transcribe(b"zz")
    assert r["error"] == "stt_unavailable" and r["reason"] == "whisper_model_missing"
