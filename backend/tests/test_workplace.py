import json

import pytest
from fastapi.testclient import TestClient

from app.book import store, views
from app.clearing import service as cs
from app.demo import scenario
from app.main import app
from app.mandate import service
from app.mandate.schema import MandateFields, Principal

@pytest.fixture()
def demo():
    scenario.reset(1)
    yield
    scenario.reset(1)

def test_ladder_open_has_no_price_and_totals_match(demo):
    lad = views.ladder("open", 10_000)
    assert lad["closed"] is False and lad["clearing_price_t"] is None
    assert lad["totals"] == {"bids": 7, "bid_t": 360, "asks": 5, "ask_t": 1000}
    assert sum(b["qty_t"] for b in lad["bands_supply"]) == 1000
    assert sum(b["qty_t"] for b in lad["bands_demand"]) <= 360
    for b in lad["bands_demand"] + lad["bands_supply"]:
        assert set(b) == {"price_from", "price_to", "qty_t"}
        assert b["price_from"] % 10_000 == 0 and b["price_to"] - b["price_from"] == 10_000
    assert [b["price_from"] for b in lad["bands_supply"]] == sorted(b["price_from"] for b in lad["bands_supply"])

def test_ladder_reveals_no_individual_mandates(demo):
    raw = json.dumps(views.ladder("open", 10_000), ensure_ascii=False)
    for mid, m in store.S.mandates.items():
        assert mid not in raw
        assert str(m.max_price_t) not in raw.replace('"price_from"', "").replace('"price_to"', "") or \
            m.max_price_t % 10_000 == 0
        if m.principal.inn:
            assert m.principal.inn not in raw
    for code in ("Namangan", "Andijan", "Qashqadaryo", "Tashkent_city", "Jizzakh"):
        assert code not in raw
    for a in store.S.asks.values():
        assert a.seller not in raw and a.offer_id not in raw
    assert "mandate_id" not in raw and "inn" not in raw

def test_ladder_band_merges_several_buyers():
    scenario.reset(0)
    f = dict(commodity="cement", grade="32.5", qty_t=10, region="Jizzakh", deadline="2026-11-15")
    for p in (512_000, 515_000, 519_000):
        pv = service.preview(MandateFields(**f, max_price_t=p), Principal(kind="ip", inn="900000001"), "", "ru")
        service.sign(pv.mandate_draft)
    lad = views.ladder("open", 10_000)
    assert lad["bands_demand"] == [{"price_from": 510_000, "price_to": 520_000, "qty_t": 30}]
    scenario.reset(1)

def test_ladder_closed_shows_one_price(demo):
    bid0 = store.open_basket_id()
    r = cs.close_basket(bid0)
    lad = views.ladder(bid0, 10_000)
    assert lad["closed"] is True and lad["clearing_price_t"] == r.clearing_price_t == 490_000
    assert lad["totals"]["bid_t"] == 360

def test_ladder_bad_args(demo):
    with pytest.raises(KeyError):
        views.ladder("B-nope", 10_000)
    with pytest.raises(ValueError):
        views.ladder("open", 0)

def test_mine_statuses_through_close(demo):
    assert [m["status"] for m in views.mine("900000001")] == ["in_basket"]
    assert views.mine("никто") == []
    cs.close_basket(store.open_basket_id())
    b1 = views.mine("900000001")[0]
    b3 = views.mine("900000002")[0]
    assert b1["status"] == "filled" and b1["deal_id"] == f"{b1['run_id']}:{b1['mandate_id']}"
    assert b1["delivered_price_t"] == 512_000 and b1["clearing_price_t"] == 490_000
    assert b1["sellers"] == ["Toshkent Conch Cement"] and b1["filled_t"] == 200
    assert b3["status"] == "unfilled" and b3["deal_id"] is None and b3["fill_at_max_price_t"] == 500_000
    assert b3["reason"] == "price_below_clearing"
    b6 = views.mine("person_2035")[0]
    assert b6["status"] == "filled" and b6["principal_kind"] == "person_2035"

def test_mine_partial_and_expired():
    scenario.reset(0)
    P = Principal(kind="person_2035", principal_id="guest-42")
    f = dict(commodity="cement", grade="32.5", region="Tashkent_region", max_price_t=600_000)
    big = service.preview(MandateFields(**f, qty_t=1100, deadline="2026-11-15"), P, "", "ru", 10 ** 9)
    service.sign(big.mandate_draft, 10 ** 9)
    old = service.preview(MandateFields(**f, qty_t=5, deadline="2026-11-08"), P, "", "ru", 10 ** 9)
    service.sign(old.mandate_draft, 10 ** 9)
    cs.close_basket(store.open_basket_id())
    st = {m["qty_t"]: m["status"] for m in views.mine("guest-42")}
    assert st == {1100: "partial", 5: "expired"}
    assert all(m["qty_t"] not in (1100, 5) for m in views.mine("person_2035"))
    scenario.reset(1)

def test_principal_id_not_in_hash_when_empty():
    a = Principal(kind="ip", inn="1").model_dump()
    assert a["principal_id"] is None
    scenario.reset(1)
    m = next(iter(store.S.mandates.values()))
    assert "principal_id" not in m.signable()["principal"]

def test_history_has_demo_past_and_new_run(demo):
    h0 = views.history()
    assert len(h0) == 3 and all(r["demo"] for r in h0)
    assert all(r["executed_qty_t"] > 0 and r["clearing_price_t"] for r in h0)
    assert [r["date"] for r in h0] == sorted((r["date"] for r in h0), reverse=True)
    assert views.demo_past_runs() == views.demo_past_runs()
    cs.close_basket(store.open_basket_id())
    h1 = views.history()
    assert h1[0]["demo"] is False and h1[0]["clearing_price_t"] == 490_000 and h1[0]["n_bids"] == 7
    for r in h1:
        assert set(r) >= {"run_id", "date", "window", "clearing_price_t", "executed_qty_t", "n_bids", "n_asks"}
    assert views.history("cement", "42.5") == []

def test_tape_basket_closed_on_top(demo):
    cs.close_basket(store.open_basket_id())
    items = store.tape(5)["items"]
    assert items[0]["kind"] == "basket_closed"
    assert items[0]["price_t"] == 490_000 and items[0]["qty_t"] == 325 and items[0]["who"] is None

def test_endpoints():
    with TestClient(app) as c:
        c.post("/demo/reset")
        lad = c.get("/book/ladder", params={"basket": "open", "step": 10000}).json()
        assert lad["clearing_price_t"] is None and lad["bands_demand"] and lad["bands_supply"]
        assert c.get("/book/ladder", params={"basket": "nope"}).status_code == 404
        assert c.get("/book/ladder", params={"step": 0}).status_code == 422
        mine = c.get("/mandate/mine", params={"principal_id": "900000001"}).json()
        assert mine["mandates"][0]["status"] == "in_basket"
        assert c.get("/mandate/mine").status_code == 422
        r = c.post("/clearing/run/open").json()
        hist = c.get("/clearing/history", params={"commodity": "cement", "grade": "32.5"}).json()
        assert hist["baskets"][0]["run_id"] == r["run_id"]
        tape = c.get("/book/tape").json()
        assert tape["items"][0]["kind"] == "basket_closed"
        c.post("/demo/reset")
