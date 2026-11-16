from __future__ import annotations

import datetime as dt

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from app.escrow import ettn_event as ettn
from app.escrow import state_machine as sm
from app.escrow import store as es

SETTINGS = settings(max_examples=200, deadline=None, stateful_step_count=30,
                    suppress_health_check=[HealthCheck.too_slow])

ALL_EVENTS = sorted({e for _, e in sm.TRANSITIONS} | {e for _, e in sm.INFO_EVENTS} | {"bogus"})
LEGAL = set(sm.TRANSITIONS.items())
times = st.datetimes(min_value=dt.datetime(2026, 11, 1), max_value=dt.datetime(2026, 12, 31))

class EscrowMachine(RuleBasedStateMachine):

    def __init__(self):
        super().__init__()
        self.esc = sm.Escrow(deal_id="R-test:M-1", mandate_id="M-1")
        self.was_final = False

    @rule(event=st.sampled_from(ALL_EVENTS), at=times, qty=st.integers(1, 10_000),
          amount=st.integers(1, 10**12), deposit=st.integers(0, 10**11))
    def fire(self, event, at, qty, amount, deposit):
        before = (self.esc.state, len(self.esc.history), self.esc.deposit, self.esc.amount)
        legal = (self.esc.state, event) in sm.TRANSITIONS or (self.esc.state, event) in sm.INFO_EVENTS
        try:
            sm.apply(self.esc, event, at, qty_t=qty, amount=amount, seller="S", deposit=deposit, reason="r")
        except sm.TransitionError:
            assert not legal or before[0] in sm.FINAL
            assert (self.esc.state, len(self.esc.history), self.esc.deposit, self.esc.amount) == before
            return
        assert legal and before[0] not in sm.FINAL
        if (before[0], event) in sm.INFO_EVENTS:
            assert self.esc.state == before[0] and len(self.esc.history) == before[1]

    @invariant()
    def state_is_known(self):
        assert self.esc.state in sm.STATES

    @invariant()
    def history_is_a_chain_of_legal_moves(self):
        prev = sm.CREATED
        for h in self.esc.history:
            assert h["from"] == prev
            assert ((h["from"], h["event"]), h["to"]) in LEGAL
            prev = h["to"]
        assert prev == self.esc.state

    @invariant()
    def money_leaves_at_most_once(self):
        outs = [h for h in self.esc.history if h["to"] in sm.FINAL]
        assert len(outs) <= 1
        released = [h for h in self.esc.history if h["to"] == sm.RELEASED]
        assert len(released) <= 1
        if released:
            i = self.esc.history.index(released[0])
            assert i > 0 and self.esc.history[i - 1]["event"] == "ettn_signed"

    @invariant()
    def final_is_forever(self):
        if self.was_final:
            assert self.esc.state in sm.FINAL
        self.was_final = self.esc.state in sm.FINAL
        if self.esc.state in sm.FINAL:
            assert sm.allowed_events(self.esc.state) == []

    @invariant()
    def no_payment_from_dispute_to_released(self):
        states = [h["to"] for h in self.esc.history]
        if sm.DISPUTED in states:
            assert sm.RELEASED not in states[states.index(sm.DISPUTED):]

TestEscrowMachine = EscrowMachine.TestCase
TestEscrowMachine.settings = SETTINGS

DEAL = "R-logic:M-2"
QTY, AMOUNT = 200, 102_400_000
factors = st.sampled_from([1.0, 0.995, 1.005, 0.994, 1.006, 0.5, 2.0])

class EscrowStoreMachine(RuleBasedStateMachine):

    def __init__(self):
        super().__init__()
        es.reset()
        esc = sm.Escrow(deal_id=DEAL, mandate_id="M-2", buyer_inn_masked="******001")
        sm.apply(esc, "mandate_signed", deposit=20_000_000)
        sm.apply(esc, "cleared", qty_t=QTY, amount=AMOUNT, seller="Toshkent Conch Cement")
        es.put(esc)
        self.payouts = 0

    def teardown(self):
        es.reset()

    def _handle(self, event, payload=None):
        before = es.get(DEAL).state
        try:
            out = es.handle(DEAL, event, payload)
        except (sm.TransitionError, ettn.EttnMismatch, ValueError):
            assert es.get(DEAL).state == before
            return None
        if out["escrow"]["state"] == sm.RELEASED and before != sm.RELEASED:
            self.payouts += 1
        return out

    @rule()
    def pay(self):
        self._handle("payment_confirmed")

    @rule()
    def shipped(self):
        self._handle("shipped")

    @rule()
    def timeout(self):
        self._handle("timeout")

    @rule(reason=st.text(max_size=20))
    def reject(self, reason):
        self._handle("ettn_rejected", {"reason": reason})

    @rule(f=factors, sigs=st.integers(0, 5))
    def ettn_signed(self, f, sigs):
        doc = ettn.demo_event(DEAL, QTY, AMOUNT, "******001", qty_factor=f)
        doc["signatures"] = sigs
        st_before = es.get(DEAL).state
        out = self._handle("ettn_signed", {"ettn": doc})
        if out is not None and not out["ignored"] and st_before == sm.PAID_IN_FULL:
            ok = ettn.within(doc["qty_t"], QTY)
            assert out["escrow"]["state"] == (sm.RELEASED if ok else sm.DISPUTED)

    @rule(other=st.sampled_from(["R-logic:M-3", "R-other:M-2"]))
    def ettn_for_foreign_deal(self, other):
        doc = ettn.demo_event(other, QTY, AMOUNT, "******001")
        before = es.get(DEAL).state
        out = self._handle("ettn_signed", {"ettn": doc})
        if before == sm.PAID_IN_FULL:
            assert out is None

    @precondition(lambda self: es.get(DEAL).state == sm.PAID_IN_FULL)
    @rule()
    def ettn_wrong_buyer(self):
        doc = ettn.demo_event(DEAL, QTY, AMOUNT, "******999")
        assert self._handle("ettn_signed", {"ettn": doc}) is None

    @invariant()
    def paid_out_at_most_once(self):
        assert self.payouts <= 1
        hist = es.get(DEAL).history
        assert sum(1 for h in hist if h["to"] in sm.FINAL) <= 1

    @invariant()
    def released_only_with_matching_ettn(self):
        esc = es.get(DEAL)
        if esc.state == sm.RELEASED:
            assert any(h["event"] == "ettn_signed" for h in esc.history)
            assert esc.dispute_reason is None

TestEscrowStoreMachine = EscrowStoreMachine.TestCase
TestEscrowStoreMachine.settings = SETTINGS
