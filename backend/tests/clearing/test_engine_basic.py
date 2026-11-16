from app.clearing.engine import run, outcome_for
from .helpers import ask, bid, book, got

def test_exact_match_trades_at_that_price():
    r = run(book([bid("b", 10, 500)], [ask("a", 10, 500)]))
    assert r.clearing_price_t == 500 and r.executed_qty_t == 10 and r.tie_break_used == "max_volume"

def test_bid_above_ask_max_volume_picks_price():
    r = run(book([bid("b", 10, 100)], [ask("a1", 5, 90), ask("a2", 10, 100)]))
    assert r.clearing_price_t == 100 and r.tie_break_used == "max_volume" and r.executed_qty_t == 10

def test_bid_below_ask_no_trade_indicative():
    r = run(book([bid("b", 10, 90)], [ask("a", 10, 100)]))
    assert r.clearing_price_t is None and r.executed_qty_t == 0
    assert r.unfilled[0].reason == "price_below_clearing"
    assert r.aggregates.best_bid == 90 and r.aggregates.best_ask == 100

def test_everyone_pays_same_base_price():
    r = run(book([bid("b1", 10, 1000), bid("b2", 10, 700)], [ask("a", 30, 500)]))
    assert {a.price_t for a in r.allocations} == {r.clearing_price_t}
    assert all(a.delivered_price_t <= 1000 for a in r.allocations)

def test_outcome_for():
    r = run(book([bid("b1", 10, 100), bid("b2", 10, 100, minute=1)], [ask("a", 15, 90)]))
    assert outcome_for(r, "b1", 10) == "filled"
    assert outcome_for(r, "b2", 10) == "partial"
    assert outcome_for(r, "zzz", 10) == "unfilled"
