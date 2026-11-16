from app.clearing.engine import run
from app.clearing.tiebreak import choose_price, round10
from decimal import Decimal
from .helpers import ask, bid, book

def test_rule1_max_volume():
    r = run(book([bid("b", 10, 100)], [ask("a1", 5, 90), ask("a2", 10, 100)]))
    assert (r.clearing_price_t, r.tie_break_used) == (100, "max_volume")

def test_rule2_min_surplus():
    r = run(book([bid("b", 10, 100)], [ask("a1", 10, 90), ask("a2", 5, 95)]))
    assert (r.clearing_price_t, r.tie_break_used) == (90, "min_surplus")

def test_rule3_market_pressure_demand_side_takes_highest():
    r = run(book([bid("b", 15, 100)], [ask("a", 10, 90)]))
    assert (r.clearing_price_t, r.tie_break_used) == (100, "market_pressure")
    assert r.aggregates.marginal_side == "demand"

def test_rule3_market_pressure_supply_side_takes_lowest():
    r = run(book([bid("b", 10, 100)], [ask("a", 15, 90)]))
    assert (r.clearing_price_t, r.tie_break_used) == (90, "market_pressure")
    assert r.aggregates.marginal_side == "supply"

def test_rule4_reference_inside_range():
    r = run(book([bid("b", 10, 100)], [ask("a", 10, 90)]), reference_price=97)
    assert (r.clearing_price_t, r.tie_break_used) == (97, "reference")

def test_rule4_reference_outside_range_clamped():
    r = run(book([bid("b", 10, 100)], [ask("a", 10, 90)]), reference_price=80)
    assert (r.clearing_price_t, r.tie_break_used) == (90, "reference")

def test_rule5_midpoint_without_reference():
    r = run(book([bid("b", 10, 100)], [ask("a", 10, 90)]))
    assert (r.clearing_price_t, r.tie_break_used) == (100, "midpoint")

def test_midpoint_rounding_and_clamp():
    assert round10(Decimal(95)) == 100
    assert round10(Decimal("92.5")) == 90
    assert choose_price([(1000, 10, 10), (1100, 10, 10)], None) == (1050, "midpoint")
    p, _ = choose_price([(1000, 10, 10), (1003, 10, 10)], None)
    assert 1000 <= p <= 1003

def test_no_candidates():
    assert choose_price([], None) == (None, "none")
    assert choose_price([(100, 0, 10)], None) == (None, "none")
