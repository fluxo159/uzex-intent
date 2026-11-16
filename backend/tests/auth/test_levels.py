import time

from fastapi.testclient import TestClient

from app.auth import settings, tokens
from app.intake import parser_llm

from .conftest import ADMIN, CODES, admin_headers, jury_client

LLM_PHRASE = "хочу цемент к моему объекту у реки"

def _fake_llm(calls):
    def fake(transcript_norm, budget=None):
        calls.append(transcript_norm)
        return "gemini", parser_llm.LLMFields(region="Namangan")
    return fake

def test_guest_by_default_gets_pid_cookie(client):
    r = client.get("/auth/me")
    assert r.status_code == 200
    me = r.json()
    assert me["level"] == "guest" and me["llm"] is True and me["voice"] is False and me["can_close_basket"] is False
    assert me["limits_left"]["llm_per_hour"] == 3
    assert me["principal_id"].startswith("g-")
    sc = r.headers["set-cookie"]
    assert settings.PID_COOKIE in sc and "HttpOnly" in sc and "SameSite=Lax" in sc
    assert client.get("/auth/me").json()["principal_id"] == me["principal_id"]

def test_code_sets_httponly_cookie_and_jury_level(client):
    r = client.post("/auth/code", json={"code": " jury-2035 "})
    assert r.status_code == 200 and r.json()["level"] == "jury"
    sc = r.headers["set-cookie"]
    assert settings.ACCESS_COOKIE in sc and "HttpOnly" in sc and "samesite=lax" in sc.lower()
    assert CODES[0] not in sc
    me = client.get("/auth/me").json()
    assert me["level"] == "jury" and me["llm"] and me["voice"]
    assert me["limits_left"]["llm_per_hour"] == 30 and me["limits_left"]["stt_per_hour"] == 20

def test_bad_code_401_and_bruteforce_429(client):
    for _ in range(10):
        assert client.post("/auth/code", json={"code": "WRONG000"}).status_code == 401
    r = client.post("/auth/code", json={"code": CODES[0]})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["detail"]["code"] == "auth_attempts" and r.json()["detail"]["message_uz"]

def test_code_extra_keys_forbidden(client):
    assert client.post("/auth/code", json={"code": CODES[0], "level": "admin"}).status_code == 422

def test_forged_or_expired_cookie_is_guest(client, monkeypatch):
    key = tokens.code_key(CODES[0])
    good = tokens.sign({"l": "jury", "c": key}, 60, "access")
    body, mac = good.split(".")
    client.cookies.set(settings.ACCESS_COOKIE, body + "." + mac[:-2] + "AA")
    assert client.get("/auth/me").json()["level"] == "guest"
    client.cookies.set(settings.ACCESS_COOKIE, tokens.sign({"l": "jury", "c": key}, 60, "pid"))
    assert client.get("/auth/me").json()["level"] == "guest"
    client.cookies.set(settings.ACCESS_COOKIE, tokens.sign({"l": "jury", "c": key}, -10, "access"))
    assert client.get("/auth/me").json()["level"] == "guest"
    client.cookies.set(settings.ACCESS_COOKIE, good)
    assert client.get("/auth/me").json()["level"] == "jury"
    monkeypatch.setenv("JURY_CODES", CODES[1])
    assert client.get("/auth/me").json()["level"] == "guest"

def test_guest_gets_llm_three_per_hour_then_offline(client, monkeypatch):
    calls = []
    monkeypatch.setattr(parser_llm, "llm_extract", _fake_llm(calls))
    client.get("/auth/me")
    for _ in range(3):
        r = client.post("/intake/parse", json={"text": LLM_PHRASE, "lang": "ru"})
        assert r.status_code == 200 and r.json()["source"] == "gemini"
    r = client.post("/intake/parse", json={"text": LLM_PHRASE, "lang": "ru"})
    assert r.status_code == 200 and r.json()["source"] == "offline" and "llm_limit" in r.json()["hints"]
    assert len(calls) == 3
    me = client.get("/auth/me").json()
    assert me["llm"] is False and me["limits_left"]["llm_per_hour"] == 0

def test_guest_llm_daily_pool_shared(client, monkeypatch):
    monkeypatch.setenv("RL_LLM_GUEST_DAY", "1")
    calls = []
    monkeypatch.setattr(parser_llm, "llm_extract", _fake_llm(calls))
    assert client.post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "gemini"
    client.cookies.clear()
    assert client.post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "offline"
    assert len(calls) == 1
    assert jury_client().post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "gemini"

def test_jury_gets_llm_and_quota_falls_back_offline(protected, monkeypatch):
    monkeypatch.setenv("RL_LLM_CODE_HOUR", "2")
    calls = []
    monkeypatch.setattr(parser_llm, "llm_extract", _fake_llm(calls))
    c = jury_client()
    for _ in range(2):
        j = c.post("/intake/parse", json={"text": LLM_PHRASE, "lang": "ru"}).json()
        assert j["source"] == "gemini" and j["fields"]["region"] == "Namangan"
    j = c.post("/intake/parse", json={"text": LLM_PHRASE, "lang": "ru"}).json()
    assert j["source"] == "offline" and "llm_limit" in j["hints"]
    assert len(calls) == 2
    c2 = jury_client(CODES[1])
    assert c2.post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "gemini"

def test_llm_daily_total_shared(protected, monkeypatch):
    monkeypatch.setenv("RL_LLM_DAY", "1")
    monkeypatch.setattr(parser_llm, "llm_extract", _fake_llm([]))
    assert jury_client().post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "gemini"
    assert jury_client(CODES[1]).post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "offline"

def test_llm_call_counts_even_if_answer_dropped(protected, monkeypatch):
    monkeypatch.setenv("RL_LLM_CODE_HOUR", "1")
    calls = []

    def provider(transcript_norm, timeout):
        calls.append(transcript_norm)
        return {}

    monkeypatch.setattr(parser_llm, "offline", lambda: False)
    monkeypatch.setattr(parser_llm, "_effective_order", lambda: ["fake"])
    monkeypatch.setitem(parser_llm.PROVIDERS, "fake", provider)
    monkeypatch.setattr(parser_llm, "cache_get", lambda t: None)
    monkeypatch.setattr(parser_llm, "cache_put", lambda *a, **k: None)
    c = jury_client()
    assert c.post("/intake/parse", json={"text": LLM_PHRASE}).json()["source"] == "offline"
    assert len(calls) == 1
    j = c.post("/intake/parse", json={"text": LLM_PHRASE}).json()
    assert "llm_limit" in j["hints"] and len(calls) == 1

def test_stt_guest_403_jury_ok(client):
    r = client.post("/intake/stt", files={"audio": ("a.webm", b"\x00\x01", "audio/webm")})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "need_jury"
    j = jury_client().post("/intake/stt", files={"audio": ("a.webm", b"\x00\x01", "audio/webm")})
    assert j.status_code == 200 and "error" in j.json()

def test_stt_limit_per_code(protected, monkeypatch):
    monkeypatch.setenv("RL_STT_CODE_HOUR", "2")
    c = jury_client()
    for _ in range(2):
        assert c.post("/intake/stt", content=b"", headers={"content-type": "audio/webm"}).status_code == 200
    r = c.post("/intake/stt", content=b"", headers={"content-type": "audio/webm"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "stt_limit"

def test_dangerous_endpoints_admin_only(client):
    jury = jury_client()
    for path in ("/demo/reset", "/demo/step/2", "/clearing/run/open", "/demo/reset?admin=1"):
        for c in (client, jury):
            r = c.post(path)
            assert r.status_code == 403, path
            assert r.json()["detail"]["code"] == "need_admin"
    assert client.post("/demo/reset", headers={"X-Admin-Token": "wrong-token-wrong-token"}).status_code == 403
    assert client.post("/demo/step/1", headers=admin_headers()).status_code == 200
    assert client.post("/clearing/run/open", headers=admin_headers()).json()["clearing_price_t"]
    assert client.post("/demo/reset", headers=admin_headers()).status_code == 200

def test_admin_query_param_gives_nothing(client):
    assert client.get("/auth/me?admin=1").json()["level"] == "guest"
    assert client.get("/auth/limits?admin=1").status_code == 403
    r = client.get("/auth/limits", headers=admin_headers())
    assert r.status_code == 200 and r.json()["limits"]["get_client"]["n"] == 120
    assert CODES[0] not in r.text

def test_short_admin_token_disables_admin(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "short")
    assert client.post("/demo/reset", headers={"X-Admin-Token": "short"}).status_code == 403

def test_bad_admin_token_bruteforce_limited(client):
    for _ in range(10):
        client.get("/auth/me", headers={"X-Admin-Token": "guess-guess-guess-guess"})
    r = client.get("/auth/me", headers={"X-Admin-Token": "guess-guess-guess-guess"})
    assert r.status_code == 429

def test_403_logged_with_ip(client, protected):
    client.post("/demo/reset", headers={"X-Real-IP": "203.0.113.7"})
    log = (protected / "access.log").read_text(encoding="utf-8")
    assert "203.0.113.7 guest POST /demo/reset 403" in log

def test_docs_off_in_prod(monkeypatch):
    from app.main import create_app
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("AUTOCLOSE_MIN", "0")
    c = TestClient(create_app())
    for p in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(p).status_code == 404, p
    assert c.get("/health").json()["protected"] is True
    monkeypatch.setenv("ENV", "dev")
    assert TestClient(create_app()).get("/openapi.json").status_code == 200

def test_prod_forces_protection_and_secure_cookie(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("AUTH_ENFORCE", "0")
    assert settings.enforce() is True and settings.cookie_secure() is True
    assert settings.autoclose_min() == 10
    monkeypatch.setenv("AUTOCLOSE_MIN", "0")
    assert settings.autoclose_min() == 0

def test_token_roundtrip_and_tamper():
    t = tokens.sign({"p": "g-1"}, 60, "pid")
    assert tokens.verify(t, "pid")["p"] == "g-1"
    assert tokens.verify(t, "access") is None
    assert tokens.verify(t + "x", "pid") is None
    assert tokens.verify("garbage", "pid") is None and tokens.verify(None, "pid") is None
    assert tokens.verify("a." * 300, "pid") is None
    assert tokens.verify(tokens.sign({"p": "g"}, -1, "pid"), "pid") is None
    assert time.time() > 0
