import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.book import store
from app.clearing import service as cs
from app.demo import scenario
from app.main import app
from app.mandate import canonical, service
from app.mandate.schema import MandateFields, Principal
from app.signing import demo_signer

NOW = dt.datetime(2026, 11, 8, 10, 0)
F = dict(commodity="cement", grade="32.5", qty_t=200, region="Namangan", deadline="2026-11-15", max_price_t=1_000_000)
P = Principal(kind="ip", inn="900000001")

@pytest.fixture()
def fresh():
    scenario.reset(0)
    yield
    scenario.reset(1)

def _sign(fields=None, principal=P, now=NOW, funds=None):
    p = service.preview(MandateFields(**(fields or F)), principal, "текст", "ru", funds, now=now)
    assert p.mandate_draft is not None, p.errors
    return service.sign(p.mandate_draft, funds)

def test_signer_roundtrip_and_tamper():
    h = canonical.sha256({"a": 1})
    r = demo_signer.sign(h, NOW)
    assert r["demo"] is True and demo_signer.verify(r)
    r2 = dict(r, hash=canonical.sha256({"a": 2}))
    assert not demo_signer.verify(r2)
    with pytest.raises(ValueError):
        demo_signer.sign("abc", NOW)

def test_basket_is_next_trading_window():
    s, e = store._windows_after(NOW)[0]
    assert (s, e) == (dt.datetime(2026, 11, 9, 11, 30), dt.datetime(2026, 11, 9, 11, 50))
    s, _ = store._windows_after(dt.datetime(2026, 11, 9, 12, 0))[0]
    assert s == dt.datetime(2026, 11, 9, 16, 30)

def test_preview_numbers(fresh):
    p = service.preview(MandateFields(**F), P, "", "ru", now=NOW)
    assert p.fees.gross_max == 200_000_000 and p.fees.exchange_fee == 403_200 and p.fees.deposit_worst == 20_000_000
    assert p.fees.delivery_min_t <= p.fees.delivery_max_t
    assert p.gate["status"] in ("ok", "warning")
    assert p.hash == canonical.sha256(p.mandate_draft.signable())

def test_preview_missing_fields_no_draft(fresh):
    p = service.preview(MandateFields(commodity="cement", region="Qashqadaryo"), P, "", "ru", now=NOW)
    codes = {(e.code, e.params.get("field")) for e in p.errors}
    assert ("missing", "qty_t") in codes and ("missing", "max_price_t") in codes
    assert p.mandate_draft is None

def test_preview_deadline_past_error(fresh):
    p = service.preview(MandateFields(**{**F, "deadline": "2026-11-01"}), P, "", "ru", now=NOW)
    assert "deadline_past" in {e.code for e in p.errors}

def test_preview_default_deadline_and_grade(fresh):
    f = {**F}
    f.pop("deadline")
    f.pop("grade")
    p = service.preview(MandateFields(**f), P, "", "ru", now=NOW)
    assert {"deadline_default", "grade_default"} <= {w.code for w in p.warnings}
    assert p.mandate_draft.execution_window.not_after == dt.date(2026, 11, 16)

def test_sign_puts_into_open_basket_and_tape(fresh):
    r = _sign()
    bk = store.get_basket(store.open_basket_id())
    assert [b.mandate_id for b in bk.bids] == [r["mandate_id"]]
    ev = store.list_events(10)
    assert any(e["kind"] == "mandate" and e["qty_t"] == 200 and e["region"] == "Namangan" for e in ev)
    assert all("inn" not in e and "display_name" not in e for e in ev)

def test_same_mandate_twice_is_same_order(fresh):
    a, b = _sign(), _sign()
    assert a["mandate_id"] == b["mandate_id"] and b.get("duplicate") is True
    bk = store.get_basket(store.open_basket_id())
    assert [x.mandate_id for x in bk.bids] == [a["mandate_id"]]

def test_expired_mandate_not_in_basket(fresh):
    r = _sign({**F, "deadline": "2026-11-08"})
    bk = store.get_basket(store.open_basket_id())
    assert r["mandate_id"] not in [b.mandate_id for b in bk.bids]

def test_close_basket_moves_unfilled_to_next(fresh):
    ok = _sign()
    low = _sign({**F, "qty_t": 5, "max_price_t": 300_000})
    bid0 = store.open_basket_id()
    res = cs.close_basket(bid0)
    assert res.clearing_price_t is not None
    assert store.S.status[ok["mandate_id"]] == "filled"
    nxt = store.open_basket_id()
    assert nxt != bid0
    assert low["mandate_id"] in [b.mandate_id for b in store.get_basket(nxt).bids]
    assert cs.close_basket(bid0).run_id == res.run_id
    assert (cs.config.LOG_DIR / f"{res.run_id}.json").exists()

def test_reset_is_deterministic():
    a = scenario.reset(2)
    ra = store.S.runs[a["run_id"]].model_dump()
    b = scenario.reset(2)
    assert a["buyers"] == b["buyers"] and store.S.runs[b["run_id"]].model_dump() == ra
    scenario.reset(1)

def test_plant_demand_only_aggregates():
    scenario.reset(1)
    from app.plant import demand
    d = demand.demand("Toshkent Conch Cement")
    assert d["price_t"] == 490_000 and d["min_lot_t"] == 50
    for r in d["regions"]:
        assert set(r) >= {"region", "qty_t", "n_mandates", "lots", "remainder_t"}
        assert r["lots"] * 50 + r["remainder_t"] == r["qty_t"]
    assert d["ready_at_your_price_t"] <= d["basket_demand_t"]
    with pytest.raises(KeyError):
        demand.demand("Нет такого завода")

def test_endpoints_flow():
    with TestClient(app) as c:
        assert c.post("/demo/reset").status_code == 200
        s = c.get("/book/basket/open").json()
        assert s["n_plants"] == 5 and s["supply_t"] == 1000 and "bids" not in s
        p = c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "ip", "inn": "900000001"}}).json()
        assert p["fees"]["exchange_fee"] == 403_200
        sg = c.post("/mandate/sign", json={"mandate": p["mandate_draft"]}).json()
        assert sg["demo"] is True and len(sg["hash"]) == 64
        assert c.get(f"/mandate/{sg['mandate_id']}").json()["status"] == "open"
        r = c.post("/clearing/run/open").json()
        assert r["clearing_price_t"] and c.get(f"/clearing/result/{r['run_id']}").status_code == 200
        assert c.get("/clearing/result/nope").status_code == 404
        assert c.get("/book/events?n=3").json()["events"]
        assert c.get("/plant/Toshkent Conch Cement/demand").status_code == 200
        assert c.get("/plant/xyz/demand").status_code == 404
        assert c.post("/demo/step/2").json()["run_id"]
        assert c.post("/demo/step/9").status_code == 422
        bad = dict(p["mandate_draft"], execution_window={"not_before": "2026-11-08T10:00:00", "not_after": "2026-11-01"})
        assert c.post("/mandate/sign", json={"mandate": bad}).status_code == 422
        c.post("/demo/reset")

def test_parallel_signing_and_close_is_consistent():
    from concurrent.futures import ThreadPoolExecutor
    scenario.reset(0)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: _sign({**F, "qty_t": 5 + i}), range(20)))
    bid0 = store.open_basket_id()
    bk = store.get_basket(bid0)
    assert len(bk.bids) == 20 and sum(b.qty_t for b in bk.bids) == sum(5 + i for i in range(20))
    with ThreadPoolExecutor(4) as ex:
        runs = list(ex.map(lambda _: cs.close_basket(bid0).run_id, range(4)))
    assert len(set(runs)) == 1
    scenario.reset(1)

def test_plants_list_keeps_sold_out_plant():
    scenario.reset(0)
    _sign({**F, "qty_t": 600, "region": "Andijan", "max_price_t": 1_000_000}, funds=200_000_000)
    cs.close_basket(store.open_basket_id())
    pl = {p["seller"]: p for p in store.plants_list()}
    assert len(pl) == 5
    sbf = pl["Shangfeng-Bridge of Friendship"]
    assert sbf["sold_out"] is True and sbf["qty_t"] == 0 and sbf["offered_t"] == 250
    from app.plant import demand
    d = demand.demand("Shangfeng-Bridge of Friendship")
    assert d["qty_t"] == 0 and d["last_run"]["sold_t"] == 250 and len(d["sellers"]) == 5
    with TestClient(app) as c:
        c.post("/demo/step/2")
        assert len(c.get("/plant").json()["plants"]) == 5
    scenario.reset(1)
