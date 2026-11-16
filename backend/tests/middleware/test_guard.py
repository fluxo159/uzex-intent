import asyncio
import datetime as dt
import json
import pathlib

from fastapi.testclient import TestClient

from app.middleware import autoclose, cache

from .conftest import admin_headers, jury_client

SNAP = pathlib.Path(__file__).parents[1] / "snapshots" / "clearing_2035.json"

def _client(ip: str) -> TestClient:
    from app.main import app
    c = TestClient(app, headers={"X-Real-IP": ip})
    c.get("/health")
    return c

def test_get_limit_per_client_429_with_retry_after(protected, monkeypatch):
    monkeypatch.setenv("RL_GET_MIN", "5")
    c = _client("198.51.100.10")
    for i in range(5):
        assert c.get("/book/basket/open").status_code == 200, i
    r = c.get("/book/basket/open")
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= 60
    d = r.json()["detail"]
    assert d["code"] == "rate_limited" and d["message_ru"] and d["message_uz"] and d["retry_after"] >= 1
    assert c.get("/health").status_code == 200
    assert _client("198.51.100.10").get("/book/basket/open").status_code == 200
    log = (protected / "access.log").read_text(encoding="utf-8")
    assert "198.51.100.10 guest GET /book/basket/open 429 get_client" in log

def test_post_limit_per_client(protected, monkeypatch):
    monkeypatch.setenv("RL_POST_MIN", "3")
    c = _client("198.51.100.11")
    for _ in range(3):
        assert c.post("/intake/parse", json={"text": "200 т"}).status_code == 200
    assert c.post("/intake/parse", json={"text": "200 т"}).status_code == 429

def test_ip_ceiling_catches_cookieless_flood(protected, monkeypatch):
    monkeypatch.setenv("RL_IP_GET_MIN", "8")
    from app.main import app
    hits = [TestClient(app, headers={"X-Real-IP": "203.0.113.99"}).get("/book/basket/open").status_code
            for _ in range(10)]
    assert hits.count(200) == 8 and hits.count(429) == 2

def test_jury_and_admin_not_blocked_by_ip_ceiling(protected, monkeypatch):
    monkeypatch.setenv("RL_IP_GET_MIN", "3")
    j = jury_client(ip="203.0.113.50")
    for _ in range(6):
        assert j.get("/book/basket/open").status_code == 200
    a = _client("203.0.113.50")
    for _ in range(6):
        assert a.get("/book/basket/open", headers=admin_headers()).status_code == 200

def test_body_over_64kb_413(protected):
    c = _client("198.51.100.12")
    r = c.post("/intake/parse", content=b'{"text":"' + b"a" * 70_000 + b'"}', headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["detail"]["code"] == "too_large"
    assert c.post("/intake/parse", json={"text": "a" * 1000}).status_code == 200

def test_audio_2mb_only_for_jury(protected):
    j = jury_client()
    ok = j.post("/intake/stt", content=b"\x00" * (1024 * 1024), headers={"content-type": "audio/webm"})
    assert ok.status_code == 200
    big = j.post("/intake/stt", content=b"\x00" * (2 * 1024 * 1024 + 10), headers={"content-type": "audio/webm"})
    assert big.status_code == 413
    g = _client("198.51.100.13").post("/intake/stt", content=b"\x00" * 1000, headers={"content-type": "audio/webm"})
    assert g.status_code == 403

def test_open_mode_keeps_old_behaviour(monkeypatch):
    monkeypatch.delenv("AUTH_ENFORCE", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    from app.main import app
    c = TestClient(app)
    assert c.post("/demo/reset").status_code == 200
    assert c.get("/auth/me").json()["protected"] is False
    assert c.get("/mandate/mine", params={"principal_id": "900000001"}).json()["mandates"]
    c.post("/demo/reset")

def test_cache_hit_and_invalidated_by_sign(protected):
    c = _client("198.51.100.14")
    first = c.get("/book/tape?n=50")
    assert first.headers.get("x-cache") is None
    again = c.get("/book/tape?n=50")
    assert again.headers.get("x-cache") == "hit" and again.json() == first.json()
    assert "set-cookie" not in {k.lower() for k in again.headers.keys()}
    F = {"commodity": "cement", "grade": "32.5", "qty_t": 120, "region": "Namangan", "deadline": "2026-11-15",
         "max_price_t": 1_000_000}
    p = c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest"}}).json()["mandate_draft"]
    assert c.post("/mandate/sign", json={"mandate": p}).status_code == 200
    after = c.get("/book/tape?n=50")
    assert after.headers.get("x-cache") is None and after.json() != first.json()

def test_autoclose_next_slot():
    assert autoclose.next_slot(dt.datetime(2026, 11, 8, 11, 31, 5), 10) == dt.datetime(2026, 11, 8, 11, 40)
    assert autoclose.next_slot(dt.datetime(2026, 11, 8, 11, 40, 0), 10) == dt.datetime(2026, 11, 8, 11, 50)
    assert autoclose.next_slot(dt.datetime(2026, 11, 8, 23, 55), 10) == dt.datetime(2026, 11, 9, 0, 0)

def test_autoclose_closes_basket_with_bids_and_skips_empty(protected):
    from app.book import store
    open_id = store.open_basket_id()
    done = autoclose.close_open_baskets()
    assert [d["basket_id"] for d in done] == [open_id] and done[0]["clearing_price_t"] == 490_000
    assert store.S.baskets[open_id].status == "closed"
    assert store.S.baskets[store.open_basket_id()].mandate_ids
    assert autoclose.close_open_baskets() == []
    c = _client("198.51.100.15")
    F = {"commodity": "cement", "grade": "32.5", "qty_t": 100, "region": "Tashkent_city", "deadline": "2026-11-15",
         "max_price_t": 900_000}
    p = c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "guest"}}).json()["mandate_draft"]
    assert c.post("/mandate/sign", json={"mandate": p}).status_code == 200
    assert len(autoclose.close_open_baskets()) == 1

def test_autoclose_task_in_lifespan(protected, monkeypatch):
    monkeypatch.setenv("AUTOCLOSE_MIN", "10")
    from app.main import app
    with TestClient(app) as c:
        me = c.get("/auth/me").json()
        assert me["autoclose"]["every_min"] == 10 and me["autoclose"]["next_at"]
        assert c.get("/book/basket/open").json()["n_plants"] == 5

def test_autoclose_loop_runs_close(protected, monkeypatch):
    monkeypatch.setenv("AUTOCLOSE_MIN", "10")
    calls = []

    def fake_close():
        calls.append(1)
        monkeypatch.setenv("AUTOCLOSE_MIN", "0")
        return [{"basket_id": "x"}]

    monkeypatch.setattr(autoclose, "next_slot", lambda now, every: now)
    monkeypatch.setattr(autoclose, "close_open_baskets", fake_close)
    asyncio.run(asyncio.wait_for(autoclose.loop(), 10))
    assert calls == [1] and autoclose._state["last"]["closed"] == [{"basket_id": "x"}]

def test_golden_scenario_under_protection(protected):
    from app.demo.scenario import scenario
    want = json.loads(SNAP.read_text(encoding="utf-8"))
    j = jury_client()
    adm = admin_headers()
    assert j.post("/demo/step/0").status_code == 403
    assert j.post("/demo/step/0", headers=adm).status_code == 200
    raw = {b["key"]: b for b in scenario()["buyers"]}
    ids = {}
    for b in j.get("/demo/scenario").json()["buyers"]:
        parsed = j.post("/intake/parse", json={"text": b["phrase"], "lang": b["lang"]}).json()
        rb = raw[b["key"]]
        body = {"fields": parsed["fields"], "principal": {"kind": rb["kind"], "inn": rb.get("inn"), "region": rb["region"]},
                "transcript_norm": parsed.get("transcript_norm", ""), "lang": b["lang"],
                "funds_available": rb.get("funds_available")}
        pv = j.post("/mandate/preview", json=body)
        assert pv.status_code == 200, (b["key"], pv.text)
        pv = pv.json()
        draft = dict(pv["mandate_draft"], created_at=rb["created_at"],
                     execution_window=dict(pv["mandate_draft"]["execution_window"], not_before=rb["created_at"]))
        sg = j.post("/mandate/sign", json={"mandate": draft, "funds_available": rb.get("funds_available")})
        assert sg.status_code == 200, (b["key"], sg.text)
        ids[b["key"]] = sg.json()["mandate_id"]
        m = want["mandates"][b["key"]]
        assert {k: pv["fees"][k] for k in m["fees"]} == m["fees"] and pv["gate"]["status"] == m["gate"]
    assert j.post("/clearing/run/open").status_code == 403
    r = j.post("/clearing/run/open", headers=adm).json()
    key_of = {v: k for k, v in ids.items()}
    assert r["clearing_price_t"] == want["clearing"]["price"] == 490_000
    assert r["executed_qty_t"] == want["clearing"]["executed_t"]
    assert sorted([[key_of[a["mandate_id"]], a["seller"], a["qty_t"], a["delivered_price_t"]]
                   for a in r["allocations"]]) == want["clearing"]["allocations"]
    assert len(j.get("/mandate/mine").json()["mandates"]) == len(ids)
    assert _client("198.51.100.77").get("/mandate/mine").json()["mandates"] == []
    cache.clear()
