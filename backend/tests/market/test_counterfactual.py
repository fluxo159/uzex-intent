import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.main import app
from app.market import counterfactual as cf

AI92_PRICES = [13_357_005, 13_360_000, 13_360_999, 13_363_999, 13_365_100]

def test_ai92_five_prices_one_price():
    data = {"date": "2026-11-06", "deals": [{"price_t": p, "qty_t": q} for p, q in zip(AI92_PRICES, [5, 3, 2, 4, 3])]}
    r = cf.ai92(data)
    assert r["uniform_price_t"] == 13_357_005
    assert r["prices"] == AI92_PRICES and r["total_qty_t"] == 17
    assert r["overpay"] == 69_234 > 0
    assert r["overpay"] == sum(d["overpay"] for d in r["deals"])
    assert r["spread_t"] == 13_365_100 - 13_357_005

def test_ai92_file_and_endpoint():
    j = TestClient(app).get("/market/counterfactual/ai92").json()
    assert j["prices"] == AI92_PRICES and j["uniform_price_t"] == 13_357_005 and j["overpay"] > 0
    assert "одну корзину" in j["caption_ru"]
    assert j["source_label_ru"] == "реестр UZEX 06.11.2026, объёмы демо"

def test_basket_counterfactual_with_delivery():
    result = {"clearing_price_t": 500_000, "allocations": [
        {"mandate_id": "m1", "offer_id": "o1", "qty_t": 10, "price_t": 500_000, "delivered_price_t": 541_000},
        {"mandate_id": "m2", "offer_id": "o1", "qty_t": 20, "price_t": 500_000, "delivered_price_t": 500_000},
    ]}
    bids = [{"mandate_id": "m1", "max_price_t": 600_000}, {"mandate_id": "m2", "max_price_t": 520_000},
            {"mandate_id": "m3", "max_price_t": 400_000}]
    r = cf.for_basket(result, bids)
    assert r["pay_as_bid_total"] == 10 * 600_000 + 20 * 520_000
    assert r["uniform_total"] == 10 * 541_000 + 20 * 500_000
    assert r["overpay"] == 10 * 59_000 + 20 * 20_000 and r["n_buyers"] == 2
    assert cf.for_basket(result, {"m1": 600_000, "m2": 520_000})["overpay"] == r["overpay"]

def test_empty_basket_zero():
    r = cf.for_basket({"clearing_price_t": None, "allocations": []}, [])
    assert r["overpay"] == 0 and r["overpay_pct"] == 0.0

def test_ceiling_below_paid_is_error_not_negative():
    with pytest.raises(cf.CounterfactualError):
        cf.overpay([(10, 400_000, 500_000)])
    with pytest.raises(cf.CounterfactualError):
        cf.for_basket({"allocations": [{"mandate_id": "x", "qty_t": 1, "price_t": 1}]}, [])

def test_huge_numbers_int():
    r = cf.overpay([(10**9, 3_000_000, 2_999_999)])
    assert r["overpay"] == 10**9 and isinstance(r["overpay"], int)

def test_uniform_price_rules():
    assert cf.uniform_price([], [(1, 1)]) is None
    assert cf.uniform_price([(100, 5)], [(200, 5)]) is None
    assert cf.uniform_price([(150, 5)], [(150, 5)]) == 150
    assert cf.uniform_price([(200, 10)], [(100, 5)]) == 200
    assert cf.uniform_price([(200, 5)], [(100, 10)]) == 100
    assert cf.uniform_price([(200, 5)], [(100, 5)]) == 150
    assert cf.uniform_price([(200, 5)], [(100, 5)], reference=180) == 200

@settings(max_examples=500, deadline=None)
@given(st.lists(st.tuples(st.integers(100, 10**6), st.integers(1, 500)), min_size=0, max_size=50),
       st.lists(st.tuples(st.integers(100, 10**6), st.integers(1, 500)), min_size=0, max_size=50))
def test_property_overpay_nonnegative_I16(bids, asks):
    p = cf.uniform_price(bids, asks)
    if p is None:
        return
    fills = [(q, b, p) for b, q in bids if b >= p]
    r = cf.overpay(fills)
    assert r["overpay"] >= 0 and r["pay_as_bid_total"] >= r["uniform_total"]

@settings(max_examples=200, deadline=None)
@given(st.lists(st.tuples(st.integers(1, 10**7), st.integers(1, 100)), min_size=1, max_size=20))
def test_property_ai92_shape(deals):
    r = cf.ai92({"deals": [{"price_t": p, "qty_t": q} for p, q in deals]})
    assert r["uniform_price_t"] == min(p for p, _ in deals)
    assert r["overpay"] >= 0
