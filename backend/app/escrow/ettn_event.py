from __future__ import annotations

import hashlib
from fractions import Fraction
from typing import Any

from .. import config

REQUIRED_SIGNATURES = 4

class EttnMismatch(Exception):
    pass

def within(actual: Any, expected: Any, tol: float | None = None) -> bool:
    tol_f = Fraction(str(config.ETTN_TOLERANCE if tol is None else tol))
    a, e = Fraction(str(actual)), Fraction(str(expected))
    return abs(a - e) <= tol_f * abs(e)

def check(event: dict, deal_id: str, qty_t: int | None, amount: int | None,
          buyer_inn_masked: str | None = None) -> dict:
    if event.get("doc", "ETTN") != "ETTN":
        return {"ok": False, "reason": "документ не ЭТТН", "diffs": {}}
    ref = event.get("deal_id")
    if ref is not None and str(ref) != str(deal_id):
        raise EttnMismatch(f"накладная для сделки {ref}, а не {deal_id}")
    if buyer_inn_masked and event.get("buyer_inn_masked") and event["buyer_inn_masked"] != buyer_inn_masked:
        raise EttnMismatch("накладная выписана другому покупателю")
    sig = int(event.get("signatures", 0))
    if sig < REQUIRED_SIGNATURES:
        return {"ok": False, "reason": f"подписей {sig} из {REQUIRED_SIGNATURES}: получатель ещё не подписал",
                "diffs": {}, "incomplete": True}
    diffs: dict[str, dict] = {}
    reasons = []
    for key, exp, label in (("qty_t", qty_t, "количества"), ("amount", amount, "суммы")):
        if exp is None or event.get(key) is None:
            continue
        got = event[key]
        if not within(got, exp):
            pct = float(Fraction(str(got)) / Fraction(str(exp)) - 1) * 100 if exp else 0.0
            diffs[key] = {"expected": exp, "got": got, "diff_pct": round(pct, 3)}
            reasons.append(f"расхождение {label}")
    if reasons:
        return {"ok": False, "reason": ", ".join(reasons), "diffs": diffs}
    return {"ok": True, "reason": None, "diffs": {}}

def demo_event(deal_id: str, qty_t: int, amount: int, buyer_inn_masked: str | None = None,
               signed_at: str | None = None, qty_factor: float = 1.0) -> dict:
    return {"doc": "ETTN", "number": "ETTN-DEMO-" + hashlib.sha256(deal_id.encode("utf-8")).hexdigest()[:6].upper(), "deal_id": deal_id,
            "buyer_inn_masked": buyer_inn_masked, "qty_t": round(qty_t * qty_factor, 3), "amount": amount,
            "signatures": REQUIRED_SIGNATURES, "signed_at": signed_at or config.DEMO_NOW, "demo": True}
