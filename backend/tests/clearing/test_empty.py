import pytest
from pydantic import ValidationError

from app.clearing.engine import run
from app.clearing.models import Bid
from .helpers import ask, bid, book

def test_empty_basket():
    r = run(book())
    assert r.clearing_price_t is None and r.executed_qty_t == 0 and r.tie_break_used == "none"

def test_only_bids():
    r = run(book([bid("b", 10, 100)]))
    assert r.clearing_price_t is None and r.unfilled[0].reason == "no_supply"

def test_only_asks():
    r = run(book([], [ask("a", 10, 100)]))
    assert r.clearing_price_t is None and r.asks_unfilled[0].reason == "no_demand"

def test_huge_numbers_no_overflow():
    big = 10 ** 9
    r = run(book([bid("b", big, 10 ** 12)], [ask("a", big, 10 ** 11)]))
    assert r.executed_qty_t == big
    assert r.allocations[0].qty_t * r.clearing_price_t >= big * 10 ** 11

@pytest.mark.parametrize("q", [2.5, 0, -5, "10"])
def test_non_integer_qty_rejected_by_schema(q):
    with pytest.raises(ValidationError):
        Bid(mandate_id="x", qty_t=q, max_price_t=100, region="R")
