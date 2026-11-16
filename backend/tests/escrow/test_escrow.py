import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.audit import sources
from app.clearing import engine
from app.clearing.models import Ask, Basket, Bid
from app.escrow import ettn_event as ettn
from app.escrow import state_machine as sm
from app.escrow import store
from app.main import app

T0 = "2026-11-09T12:00:00"

def matched(qty=20, amount=20 * 531_000):
    e = sm.Escrow(deal_id="R1:m1", mandate_id="m1")
    sm.apply(e, "mandate_signed", T0, deposit=2_000_000)
    sm.apply(e, "cleared", T0, qty_t=qty, amount=amount, seller="Toshkent Conch Cement")
    return e

@pytest.fixture(autouse=True)
def clean():
    store.reset()
    sources.reset()
    yield
    store.reset()
    sources.reset()

def test_green_path():
    e = matched()
    assert e.state == sm.MATCHED and e.deadline_kind == "payment" and e.deadline == "2026-11-10T12:00"
    sm.apply(e, "payment_confirmed", T0)
    store.put(e)
    r = store.handle("R1:m1", "ettn_signed", {"ettn": ettn.demo_event("R1:m1", 20, 20 * 531_000)})
    assert r["escrow"]["state"] == sm.RELEASED
    assert [h["to"] for h in e.history] == [sm.DEPOSIT_HELD, sm.MATCHED, sm.PAID_IN_FULL, sm.DELIVERED, sm.RELEASED]
    assert e.deadline_kind == "payout_to_seller"

def test_red_path_rejected_dispute_3_days():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    sm.apply(e, "ettn_rejected", "2026-11-12T10:00:00", reason="мешки порваны")
    assert e.state == sm.DISPUTED and e.dispute_reason == "мешки порваны"
    assert e.deadline_kind == "dispute" and e.deadline == "2026-11-17T10:00"

def test_payment_timeout_cancelled():
    e = matched()
    sm.apply(e, "timeout", T0)
    assert e.state == sm.CANCELLED and "задаток покупателя → продавцу" in e.history[-1]["note"]
    with pytest.raises(sm.TransitionError):
        sm.apply(e, "payment_confirmed", T0)

@pytest.mark.parametrize("factor,state", [(1.004, sm.RELEASED), (1.005, sm.RELEASED), (0.995, sm.RELEASED),
                                          (1.006, sm.DISPUTED), (0.994, sm.DISPUTED)])
def test_qty_tolerance(factor, state):
    e = matched(qty=1000, amount=1000 * 531_000)
    sm.apply(e, "payment_confirmed", T0)
    store.put(e)
    doc = ettn.demo_event("R1:m1", 1000, 1000 * 531_000, qty_factor=factor)
    r = store.handle("R1:m1", "ettn_signed", {"ettn": doc})
    assert r["escrow"]["state"] == state
    if state == sm.DISPUTED:
        assert "расхождение количества" in r["escrow"]["dispute_reason"]

def test_within_boundary_exact():
    assert ettn.within(1005, 1000) and ettn.within(995, 1000)
    assert not ettn.within(1005.0001, 1000)
    assert ettn.within(20.1, 20)

def test_amount_mismatch_disputed():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    store.put(e)
    doc = ettn.demo_event("R1:m1", 20, 20 * 600_000)
    r = store.handle("R1:m1", "ettn_signed", {"ettn": doc})
    assert r["escrow"]["state"] == sm.DISPUTED and "суммы" in r["escrow"]["dispute_reason"]

def test_repeated_ettn_ignored_with_log():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    store.put(e)
    store.handle("R1:m1", "ettn_signed", {})
    r = store.handle("R1:m1", "ettn_signed", {})
    assert r["ignored"] is True and r["escrow"]["state"] == sm.RELEASED
    assert any(x.get("ignored") for x in r["escrow"]["log"])

def test_I15_no_transitions_from_released():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    sm.apply(e, "ettn_signed", T0)
    assert e.state == sm.RELEASED
    for ev in ("ettn_rejected", "payment_confirmed", "timeout", "cleared", "mandate_signed", "ettn_signed", "shipped"):
        with pytest.raises(sm.TransitionError):
            sm.apply(e, ev, T0)
    assert e.state == sm.RELEASED
    assert sm.allowed_events(sm.RELEASED) == []
    for final in sm.FINAL:
        assert not any(s == final for s, _ in sm.TRANSITIONS)

def test_other_deal_event_mismatch():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    store.put(e)
    with pytest.raises(ettn.EttnMismatch):
        store.handle("R1:m1", "ettn_signed", {"ettn": ettn.demo_event("R9:zz", 20, 20 * 531_000)})
    assert e.state == sm.PAID_IN_FULL

def test_incomplete_signatures_rejected():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    store.put(e)
    doc = dict(ettn.demo_event("R1:m1", 20, 20 * 531_000), signatures=3)
    with pytest.raises(ValueError):
        store.handle("R1:m1", "ettn_signed", {"ettn": doc})
    assert e.state == sm.PAID_IN_FULL

def test_shipped_grey_path_6_hours():
    e = matched()
    sm.apply(e, "payment_confirmed", T0)
    sm.apply(e, "shipped", "2026-11-13T15:00:00")
    assert e.state == sm.PAID_IN_FULL and "2026-11-16T12:00" in e.grey_path

def test_business_days_skip_weekend():
    assert sm.add_business_days(dt.datetime(2026, 11, 13, 10), 1) == dt.datetime(2026, 11, 16, 10)

def _run():
    b = Basket(basket_id="B1", bids=[Bid(mandate_id="m1", qty_t=20, max_price_t=1_000_000, region="Namangan"),
                                     Bid(mandate_id="m2", qty_t=10, max_price_t=100_000, region="Namangan")],
               asks=[Ask(offer_id="o1", seller="Toshkent Conch Cement", qty_t=300, min_price_t=490_000,
                         warehouse_region="Tashkent_region")])
    res = engine.run(b, {("Tashkent_region", "Namangan"): 41_000})
    sources.register_run(res, b)
    return res

def test_endpoints_full_flow():
    res = _run()
    did = f"{res.run_id}:m1"
    c = TestClient(app)
    j = c.get(f"/escrow/{did}").json()
    assert j["state"] == sm.MATCHED and j["qty_t"] == 20 and j["amount"] == 20 * (res.clearing_price_t + 41_000)
    assert j["demo"] is True and j["deposit"] == 2_000_000
    assert c.get("/escrow/m1").json()["deal_id"] == did
    assert c.post(f"/escrow/{did}/event", json={"type": "payment_confirmed"}).json()["escrow"]["state"] == sm.PAID_IN_FULL
    r = c.post(f"/escrow/{did}/event", json={"type": "ettn_signed", "qty_factor": 1.004}).json()
    assert r["escrow"]["state"] == sm.RELEASED
    assert c.post(f"/escrow/{did}/event", json={"type": "ettn_rejected", "reason": "x"}).status_code == 409
    assert c.post(f"/escrow/{did}/event", json={"type": "ettn_signed"}).json()["ignored"] is True

def test_endpoints_unfilled_stays_deposit_held_and_404():
    res = _run()
    c = TestClient(app)
    assert c.get(f"/escrow/{res.run_id}:m2").json()["state"] == sm.DEPOSIT_HELD
    assert c.get("/escrow/R-nope:m1").status_code == 404
    assert c.post("/escrow/R-nope:m1/event", json={"type": "timeout"}).status_code == 404
    did = f"{res.run_id}:m1"
    c.post(f"/escrow/{did}/event", json={"type": "payment_confirmed"})
    bad = ettn.demo_event("other-deal", 20, 1)
    assert c.post(f"/escrow/{did}/event", json={"type": "ettn_signed", "ettn": bad}).status_code == 404
    assert c.post(f"/escrow/{did}/event", json={"type": "bogus"}).status_code == 422
