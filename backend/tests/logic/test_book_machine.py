from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from app import config
from app.book import store
from app.clearing import service as cs
from app.clearing.delivery import demo_tariff, tariff_t
from app.clearing.models import Ask
from app.demo import scenario
from app.mandate import service
from app.mandate.schema import MandateFields, Principal

SETTINGS = settings(max_examples=200, deadline=None, stateful_step_count=25,
                    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])

REGIONS = ["Namangan", "Qashqadaryo", "Tashkent_region", "Tashkent_city", "Samarqand", "Jizzakh", "Fergana"]
P = Principal(kind="ip", inn="900000001")
FUNDS = 10**15
NOW = config.now()
DEADLINES = [NOW.date(), NOW.date() + dt.timedelta(days=1), NOW.date() + dt.timedelta(days=2),
             NOW.date() + dt.timedelta(days=7)]

@pytest.fixture(autouse=True, scope="module")
def _quiet_logs():
    old = config.LOG_DIR
    with tempfile.TemporaryDirectory() as d:
        config.LOG_DIR = Path(d)
        yield
    config.LOG_DIR = old
    scenario.reset(1)

class BookMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        scenario.reset(0)
        self.qty: dict[str, int] = {}
        self.ask_qty: dict[str, int] = {a: x.qty_t for a, x in store.S.asks.items()}
        self.ask_min: dict[str, int] = {a: x.min_price_t for a, x in store.S.asks.items()}
        self.closed: dict[str, tuple[str, tuple[str, ...]]] = {}
        self.n_ask = 0

    @rule(qty=st.integers(1, 400), price=st.integers(1, 1_200_000), region=st.sampled_from(REGIONS),
          deadline=st.sampled_from(DEADLINES), grade=st.sampled_from(["32.5", "32.5", "42.5"]))
    def sign(self, qty, price, region, deadline, grade):
        f = MandateFields(commodity="cement", grade=grade, qty_t=qty, region=region, deadline=deadline,
                          max_price_t=price)
        p = service.preview(f, P, "", "ru", FUNDS, now=NOW)
        if p.mandate_draft is None:
            return
        out = service.sign(p.mandate_draft, FUNDS)
        mid = out["mandate_id"]
        self.qty[mid] = qty
        assert out["basket_id"] not in self.closed
        assert store.S.baskets[out["basket_id"]].status == "open"

    @rule(qty=st.integers(1, 300), price=st.integers(300_000, 700_000), region=st.sampled_from(REGIONS),
          lot=st.sampled_from([1, 50, 55, 200]))
    def add_ask(self, qty, price, region, lot):
        self.n_ask += 1
        oid = f"A-H{self.n_ask}"
        store.add_ask(Ask(offer_id=oid, seller=f"Plant {self.n_ask}", qty_t=qty, min_price_t=price,
                          warehouse_region=region, min_lot_t=lot, created_at=NOW))
        self.ask_qty[oid] = qty
        self.ask_min[oid] = price

    @rule(grade=st.sampled_from(["32.5", "42.5"]))
    def close_open(self, grade):
        bid = store.open_basket_id("cement", grade)
        r = cs.close_basket(bid)
        snapshot = tuple(store.S.baskets[bid].mandate_ids)
        self.closed[bid] = (r.run_id, snapshot)

    @rule(data=st.data())
    def reclose(self, data):
        if not self.closed:
            return
        bid = data.draw(st.sampled_from(sorted(self.closed)))
        r = cs.close_basket(bid)
        assert r.run_id == self.closed[bid][0]

    @invariant()
    def closed_baskets_frozen(self):
        for bid, (run_id, snap) in self.closed.items():
            bi = store.S.baskets[bid]
            assert bi.status == "closed" and bi.run_id == run_id
            assert tuple(bi.mandate_ids) == snap

    @invariant()
    def each_run_is_sane(self):
        tar = demo_tariff()
        for run_id, r in store.S.runs.items():
            bk = store.S.run_baskets[run_id]
            bids = {b.mandate_id: b for b in bk.bids}
            asks = {a.offer_id: a for a in bk.asks}
            prices = {a.price_t for a in r.allocations}
            assert len(prices) <= 1
            if r.allocations:
                assert prices == {r.clearing_price_t}
            for a in r.allocations:
                b = bids[a.mandate_id]
                assert a.qty_t >= 1
                assert a.tariff_t == tariff_t(tar, asks[a.offer_id].warehouse_region, b.region)
                assert a.delivered_price_t == a.price_t + a.tariff_t <= b.max_price_t
                assert a.price_t >= asks[a.offer_id].min_price_t
                assert store.S.mandates[a.mandate_id].expiry >= store.S.baskets[r.basket_id].window_end
            got: dict[str, int] = {}
            for a in r.allocations:
                got[a.mandate_id] = got.get(a.mandate_id, 0) + a.qty_t
            left = {}
            for u in r.unfilled:
                left[u.mandate_id] = left.get(u.mandate_id, 0) + u.qty_t
            for mid, b in bids.items():
                assert got.get(mid, 0) + left.get(mid, 0) == b.qty_t
            sold: dict[str, int] = {}
            for a in r.allocations:
                sold[a.offer_id] = sold.get(a.offer_id, 0) + a.qty_t
            for oid, a in asks.items():
                assert sold.get(oid, 0) <= a.qty_t
            assert r.executed_qty_t == sum(got.values()) == sum(sold.values())
            partial_b = [m for m in got if 0 < got[m] < bids[m].qty_t and left.get(m, 0) and
                         {u.reason for u in r.unfilled if u.mandate_id == m} <= {"no_supply"}]
            assert len(partial_b) <= 1

    @invariant()
    def mandates_never_overfilled(self):
        filled: dict[str, int] = {}
        for r in store.S.runs.values():
            for a in r.allocations:
                filled[a.mandate_id] = filled.get(a.mandate_id, 0) + a.qty_t
        for mid, q in self.qty.items():
            f = filled.get(mid, 0)
            assert f <= q
            assert store.S.remaining[mid] == q - f
            assert (store.S.status[mid] == "filled") == (q - f == 0)

    @invariant()
    def plants_never_oversold(self):
        sold: dict[str, int] = {}
        for r in store.S.runs.values():
            for a in r.allocations:
                sold[a.offer_id] = sold.get(a.offer_id, 0) + a.qty_t
        for oid, q in self.ask_qty.items():
            s = sold.get(oid, 0)
            assert s <= q
            cur = store.S.asks.get(oid)
            assert (cur.qty_t if cur else 0) == q - s

    @invariant()
    def one_open_basket_per_grade(self):
        for g in ("32.5", "42.5"):
            open_ = [b for b in store.S.baskets.values() if b.status == "open" and b.grade == g]
            assert len(open_) <= 1

    @invariant()
    def expired_mandates_not_in_next_basket_bids(self):
        for g in ("32.5", "42.5"):
            bid = store.S.open_by_key.get(("cement", g))
            if bid is None:
                continue
            bk = store.get_basket(bid)
            for b in bk.bids:
                assert store.S.mandates[b.mandate_id].expiry >= store.S.baskets[bid].window_end

TestBookMachine = BookMachine.TestCase
TestBookMachine.settings = SETTINGS
