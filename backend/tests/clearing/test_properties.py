import datetime as dt

from hypothesis import given, settings, strategies as st

from app.clearing.engine import run
from app.clearing.models import Ask, Basket, Bid

T0 = dt.datetime(2026, 11, 8, 10, 0)
REG = ["R1", "R2", "R3"]
TAR = {("R1", "R2"): 20, ("R1", "R3"): 50, ("R2", "R3"): 35}

bids_st = st.lists(st.tuples(st.integers(1, 500), st.integers(100, 10 ** 6), st.integers(0, 3), st.sampled_from(REG)),
                   max_size=25)
asks_st = st.lists(st.tuples(st.integers(1, 500), st.integers(100, 10 ** 6), st.integers(0, 3), st.sampled_from(REG),
                             st.integers(0, 60)), max_size=25)

def mk(bids, asks, regions=True, lots=False):
    b = [Bid(mandate_id=f"b{i:02d}", qty_t=q, max_price_t=p, region=r if regions else "R1",
             created_at=T0 + dt.timedelta(minutes=m)) for i, (q, p, m, r) in enumerate(bids)]
    a = [Ask(offer_id=f"a{i:02d}", seller=f"s{i}", qty_t=q, min_price_t=p, warehouse_region=r if regions else "R1",
             min_lot_t=lot if lots else 1, created_at=T0 + dt.timedelta(minutes=m))
         for i, (q, p, m, r, lot) in enumerate(asks)]
    return Basket(basket_id="P", bids=b, asks=a)

def check_common(bk, r):
    bids = {b.mandate_id: b for b in bk.bids}
    asks = {a.offer_id: a for a in bk.asks}
    assert {x.price_t for x in r.allocations} <= ({r.clearing_price_t} if r.clearing_price_t is not None else set())
    for x in r.allocations:
        assert x.delivered_price_t <= bids[x.mandate_id].max_price_t
        assert x.price_t >= asks[x.offer_id].min_price_t
    tot = sum(x.qty_t for x in r.allocations)
    assert tot == r.executed_qty_t
    assert tot == sum(b.qty_t for b in bk.bids) - sum(u.qty_t for u in r.unfilled)
    assert tot == sum(a.qty_t for a in bk.asks) - sum(u.qty_t for u in r.asks_unfilled)
    for mid, b in bids.items():
        assert sum(x.qty_t for x in r.allocations if x.mandate_id == mid) <= b.qty_t
    for oid, a in asks.items():
        assert sum(x.qty_t for x in r.allocations if x.offer_id == oid) <= a.qty_t
    if bk.bids and bk.asks and r.aggregates.best_bid is not None:
        if r.aggregates.best_bid < min(a.min_price_t for a in bk.asks):
            assert r.clearing_price_t is None and not r.allocations

@settings(max_examples=500, deadline=None)
@given(bids_st, asks_st)
def test_invariants_single_region_xetra(bids, asks):
    bk = mk(bids, asks, regions=False)
    r = run(bk)
    check_common(bk, r)
    if r.clearing_price_t is not None:
        p = r.clearing_price_t

        def D(x):
            return sum(b.qty_t for b in bk.bids if b.max_price_t >= x)

        def S(x):
            return sum(a.qty_t for a in bk.asks if a.min_price_t <= x)

        cands = {b.max_price_t for b in bk.bids} | {a.min_price_t for a in bk.asks}
        assert r.executed_qty_t == min(D(p), S(p)) == max(min(D(c), S(c)) for c in cands)
    pb = [b for b in bk.bids if 0 < sum(x.qty_t for x in r.allocations if x.mandate_id == b.mandate_id) < b.qty_t]
    pa = [a for a in bk.asks if 0 < sum(x.qty_t for x in r.allocations if x.offer_id == a.offer_id) < a.qty_t]
    assert len(pb) <= 1 and len(pa) <= 1

@settings(max_examples=500, deadline=None)
@given(bids_st, asks_st, st.randoms(use_true_random=False))
def test_invariants_with_delivery_and_lots_permutation(bids, asks, rnd):
    bk = mk(bids, asks, regions=True, lots=True)
    r = run(bk, TAR)
    check_common(bk, r)
    for g in r.lot_groups:
        assert g.qty_t >= g.min_lot_t
    b2, a2 = list(bk.bids), list(bk.asks)
    rnd.shuffle(b2)
    rnd.shuffle(a2)
    r2 = run(Basket(basket_id="P", bids=b2, asks=a2), TAR)
    assert r2.model_dump() == r.model_dump()
