from __future__ import annotations

from typing import Any

from .. import config
from ..audit import sources
from ..market.objects import g, items
from ..mandate import fees
from . import ettn_event as ettn
from . import state_machine as sm

_STORE: dict[str, sm.Escrow] = {}

class NotFound(KeyError):
    pass

def reset() -> None:
    _STORE.clear()

def _from_run(did: str) -> sm.Escrow | None:
    try:
        run_id, mandate_id = sources.split_deal_id(did)
    except KeyError:
        return None
    run = sources.get_run(run_id)
    if run is None:
        return None
    result, basket = run["result"], run["basket"]
    bid = next((b for b in items(basket, "bids") if str(g(b, "mandate_id")) == mandate_id), None)
    if bid is None:
        return None
    did = sources.deal_id(run_id, mandate_id)
    info = sources.mandate_info(mandate_id)
    esc = sm.Escrow(deal_id=did, mandate_id=mandate_id, buyer_inn_masked=info.get("inn_masked"))
    deposit = info.get("deposit")
    if deposit is None:
        deposit = fees.deposit(fees.gross_max(int(g(bid, "qty_t")), int(g(bid, "max_price_t"))))
    sm.apply(esc, "mandate_signed", deposit=deposit)
    mine = [a for a in items(result, "allocations") if str(g(a, "mandate_id")) == mandate_id]
    if mine:
        qty = sum(int(g(a, "qty_t")) for a in mine)
        amount = sum(int(g(a, "qty_t")) * int(g(a, "delivered_price_t", g(a, "price_t"))) for a in mine)
        sellers = sorted({str(g(a, "seller")) for a in mine if g(a, "seller")})
        sm.apply(esc, "cleared", qty_t=qty, amount=amount, seller=", ".join(sellers) or None)
    return esc

def get(did: str) -> sm.Escrow:
    esc = _STORE.get(did)
    if esc is None:
        esc = _from_run(did)
        if esc is None:
            raise NotFound(did)
        _STORE[esc.deal_id] = esc
        _STORE[did] = esc
    return esc

def put(esc: sm.Escrow) -> sm.Escrow:
    _STORE[esc.deal_id] = esc
    return esc

def handle(did: str, event: str, payload: dict | None = None, at: Any = None) -> dict:
    payload = dict(payload or {})
    esc = get(did)
    t = at or payload.get("at") or payload.get("signed_at")
    if event == "ettn_signed":
        if esc.state in (sm.DELIVERED, sm.RELEASED) and any(h["event"] == "ettn_signed" for h in esc.history):
            esc.log.append({"event": event, "ignored": True, "why": "повторная накладная — игнор",
                            "number": payload.get("number")})
            return {"escrow": esc.to_dict(), "ignored": True, "check": None}
        if esc.state != sm.PAID_IN_FULL:
            raise sm.TransitionError(f"событие {event} недопустимо в состоянии {esc.state}")
        doc = payload.get("ettn") or payload
        if not doc.get("qty_t") and not doc.get("amount"):
            doc = ettn.demo_event(esc.deal_id, esc.qty_t or 0, esc.amount or 0, esc.buyer_inn_masked)
        res = ettn.check(doc, esc.deal_id, esc.qty_t, esc.amount, esc.buyer_inn_masked)
        if res.get("incomplete"):
            raise ValueError(res["reason"])
        if not res["ok"]:
            sm.dispute(esc, res["reason"], t)
            esc.log.append({"event": event, "auto_dispute": True, "diffs": res["diffs"]})
            return {"escrow": esc.to_dict(), "ignored": False, "check": res}
        sm.apply(esc, "ettn_signed", t)
        return {"escrow": esc.to_dict(), "ignored": False, "check": res}
    sm.apply(esc, event, t, **{k: v for k, v in payload.items() if k not in ("at",)})
    return {"escrow": esc.to_dict(), "ignored": False, "check": None}

def all_deals() -> list[dict]:
    seen, out = set(), []
    for esc in _STORE.values():
        if id(esc) not in seen:
            seen.add(id(esc))
            out.append(esc.to_dict())
    return out

TOLERANCE = config.ETTN_TOLERANCE
