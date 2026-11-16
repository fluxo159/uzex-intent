import json

from fastapi.testclient import TestClient

from .conftest import admin_headers, jury_client

F = {"commodity": "cement", "grade": "32.5", "qty_t": 200, "region": "Namangan", "deadline": "2026-11-15",
     "max_price_t": 1_000_000, "payment_terms": "after_delivery"}

def _sign(c: TestClient, principal: dict | None = None, **fields) -> dict:
    p = c.post("/mandate/preview", json={"fields": {**F, **fields}, "principal": principal or {"kind": "guest"}})
    assert p.status_code == 200, p.text
    s = c.post("/mandate/sign", json={"mandate": p.json()["mandate_draft"]})
    return {"status": s.status_code, **(s.json() if s.headers.get("content-type", "").startswith("application/json") else {})}

def _new_client(ip: str = "198.51.100.1") -> TestClient:
    from app.main import app
    c = TestClient(app, headers={"X-Real-IP": ip})
    c.get("/auth/me")
    return c

def test_mine_only_own_by_cookie(protected):
    a, b = _new_client("198.51.100.1"), _new_client("198.51.100.2")
    pid_a = a.get("/auth/me").json()["principal_id"]
    pid_b = b.get("/auth/me").json()["principal_id"]
    s = _sign(a, {"kind": "guest", "principal_id": pid_b})
    assert s["status"] == 200
    mine_a = a.get("/mandate/mine").json()
    assert mine_a["principal_id"] == pid_a and [m["mandate_id"] for m in mine_a["mandates"]] == [s["mandate_id"]]
    assert a.get("/mandate/mine", params={"principal_id": pid_a}).json()["mandates"]
    assert b.get("/mandate/mine", params={"principal_id": pid_a}).json()["mandates"] == []
    assert b.get("/mandate/mine").json()["mandates"] == []
    assert b.get("/mandate/mine", params={"principal_id": "900000001"}).json()["mandates"] == []
    assert b.get(f"/mandate/{s['mandate_id']}").status_code == 404
    assert a.get(f"/mandate/{s['mandate_id']}").status_code == 200
    assert b.get(f"/mandate/{s['mandate_id']}", headers=admin_headers()).status_code == 200
    assert b.get("/mandate/mine", params={"principal_id": pid_a}, headers=admin_headers()).json()["mandates"]

def test_ladder_and_tape_have_no_identifiers(protected):
    a = _new_client()
    pid = a.get("/auth/me").json()["principal_id"]
    _sign(a, {"kind": "company", "inn": "900000011", "display_name": "ООО Тест"})
    for path in ("/book/ladder", "/book/tape?n=50", "/book/basket/open"):
        r = a.get(path)
        assert r.status_code == 200, path
        text = json.dumps(r.json(), ensure_ascii=False)
        for bad in ("principal", "inn", "900000", "ООО Тест", "mandate_id", pid):
            assert bad not in text, (path, bad)

def test_numbers_out_of_range_422(protected):
    c = _new_client()
    for fields in ({"qty_t": 0}, {"qty_t": 10_001}, {"max_price_t": 9_999}, {"max_price_t": 100_000_001}):
        r = c.post("/mandate/preview", json={"fields": {**F, **fields}, "principal": {"kind": "guest"}})
        assert r.status_code == 422, fields
        assert "от" in json.dumps(r.json(), ensure_ascii=False)
    p = c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest"}}).json()["mandate_draft"]
    big = dict(p, line_items=[dict(p["line_items"][0], qty_t=50_000)])
    assert c.post("/mandate/sign", json={"mandate": big}).status_code == 422
    cheap = dict(p, amount_range={"max_price_t": 1, "currency": "UZS"})
    assert c.post("/mandate/sign", json={"mandate": cheap}).status_code == 422
    ok = c.post("/mandate/preview", json={"fields": {**F, "qty_t": 10_000, "max_price_t": 10_000},
                                          "principal": {"kind": "guest"}})
    assert ok.status_code == 200

def test_unknown_keys_422(protected):
    c = _new_client()
    assert c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest"}, "admin": True}).status_code == 422
    assert c.post("/mandate/preview", json={"fields": {**F, "price": 1}}).status_code == 422
    assert c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest", "level": "admin"}}).status_code == 422
    p = c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest"}}).json()["mandate_draft"]
    assert c.post("/mandate/sign", json={"mandate": {**p, "status": "filled"}}).status_code == 422
    assert c.post("/intake/parse", json={"text": "200 тонн", "llm": True}).status_code == 422

def test_guest_sign_limit_5_per_hour(protected):
    c = _new_client()
    for i in range(5):
        assert _sign(c)["status"] == 200, i
    r = _sign(c)
    assert r["status"] == 429 and r["detail"]["code"] == "sign_limit"
    assert "5" in r["detail"]["message_ru"] and r["detail"]["message_uz"]
    assert _sign(_new_client("198.51.100.9"))["status"] == 200
    assert c.post("/mandate/sign", headers=admin_headers(), json={
        "mandate": c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest"}}).json()["mandate_draft"]}).status_code == 200

def test_sign_limit_per_ip(protected, monkeypatch):
    monkeypatch.setenv("RL_SIGN_IP_HOUR", "3")
    for i in range(3):
        assert _sign(_new_client("192.0.2.50"))["status"] == 200, i
    r = _sign(_new_client("192.0.2.50"))
    assert r["status"] == 429 and r["detail"]["code"] == "sign_ip_limit"

def test_jury_signs_more_than_guest(protected):
    c = jury_client()
    for i in range(7):
        assert _sign(c)["status"] == 200, i

def test_guest_parse_limit_10_per_min(protected):
    c = _new_client()
    for i in range(10):
        assert c.post("/intake/parse", json={"text": "200 тонн цемента"}).status_code == 200, i
    r = c.post("/intake/parse", json={"text": "200 тонн цемента"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "parse_limit"
    assert int(r.headers["retry-after"]) >= 1
    j = jury_client()
    for _ in range(12):
        assert j.post("/intake/parse", json={"text": "200 тонн цемента"}).status_code == 200

def test_long_phrase_truncated_not_500(protected):
    c = _new_client()
    r = c.post("/intake/parse", json={"text": "цемент " * 200})
    assert r.status_code == 200 and "text_truncated" in r.json()["hints"]
    assert len(r.json()["transcript_norm"]) <= 500
