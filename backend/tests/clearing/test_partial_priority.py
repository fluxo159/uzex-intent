from app.clearing.engine import run
from .helpers import ask, bid, book, got

def test_demand_exceeds_supply_by_one_tonne():
    r = run(book([bid("b1", 60, 100, minute=0), bid("b2", 41, 100, minute=1)], [ask("a", 100, 90)]))
    assert r.executed_qty_t == 100
    assert got(r, "b1") == 60 and got(r, "b2") == 40
    assert [(u.mandate_id, u.qty_t, u.reason) for u in r.unfilled] == [("b2", 1, "no_supply")]

def test_marginal_is_by_price_then_time():
    r = run(book([bid("b_low", 50, 95, minute=0), bid("b_hi", 60, 100, minute=5)], [ask("a", 100, 90)]))
    assert got(r, "b_hi") == 60 and got(r, "b_low") == 40

def test_same_price_earlier_time_first():
    r = run(book([bid("late", 10, 100, minute=9), bid("early", 10, 100, minute=1)], [ask("a", 15, 90)]))
    assert got(r, "early") == 10 and got(r, "late") == 5

def test_same_price_same_time_by_mandate_id_stable():
    bids = [bid("m-b", 10, 100), bid("m-a", 10, 100)]
    for order in (bids, bids[::-1]):
        r = run(book(order, [ask("a", 15, 90)]))
        assert got(r, "m-a") == 10 and got(r, "m-b") == 5

def test_asks_priority_cheaper_first():
    r = run(book([bid("b", 15, 100)], [ask("exp", 10, 95), ask("cheap", 10, 90)]))
    sold = {a.offer_id: a.qty_t for a in r.allocations}
    assert sold.get("cheap") == 10 and sold.get("exp") == 5
