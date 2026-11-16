import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.intake import parser_offline as po
from app.intake.router import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_parse_all_phrases_fast():
    for item in po.phrases():
        t0 = time.perf_counter()
        r = client.post("/intake/parse", json={"text": item["text"], "lang": item["lang"]})
        dt = time.perf_counter() - t0
        assert r.status_code == 200
        assert r.json()["fields"] == item["expected"]["fields"]
        assert dt < 0.3, (item["id"], dt)

def test_parse_lang_hint_alias():
    r = client.post("/intake/parse", json={"text": "200 тонн", "lang_hint": "uz"})
    assert r.status_code == 200 and r.json()["lang"] == "uz"

def test_parse_garbage_no_500():
    for body in ({}, {"text": None}, {"text": "🔥" * 100}, {"text": "x" * 20000}):
        r = client.post("/intake/parse", json=body)
        assert r.status_code == 200
        assert "qty_t" in r.json()["missing_fields"]

def test_stt_no_backend_no_500():
    r = client.post("/intake/stt", files={"audio": ("a.webm", b"\x00\x01", "audio/webm")})
    assert r.status_code == 200 and r.json()["error"] == "stt_unavailable"

def test_stt_raw_body_empty():
    r = client.post("/intake/stt", content=b"", headers={"content-type": "audio/webm"})
    assert r.status_code == 200 and r.json()["error"] == "empty_audio"
