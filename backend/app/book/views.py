from __future__ import annotations

import datetime as dt
import random
from functools import lru_cache

from .. import config
from ..clearing.delivery import demo_tariff, tariff_t
from ..clearing.models import Basket, Bid
from . import store

def _band(p: int, step: int) -> int:
    return (p // step) * step

def ladder(basket: str = "open", step: int = 10_000) -> dict:
    if step < 1:
        raise ValueError("шаг полосы должен быть положительным")
    with store.LOCK:
        bid_ = store.open_basket_id() if basket == "open" else basket
        bi = store.S.baskets.get(bid_)
        if bi is None:
            raise KeyError(basket)
        closed = bi.status == "closed" and bi.run_id is not None
        bk: Basket = store.S.run_baskets[bi.run_id] if closed else store.get_basket(bid_)
        price = store.S.runs[bi.run_id].clearing_price_t if closed else None
    tar = demo_tariff()
    dem: dict[int, int] = {}
    for b in bk.bids:
        effs = [b.max_price_t - t for a in bk.asks if (t := tariff_t(tar, a.warehouse_region, b.region)) is not None]
        if not effs or max(effs) <= 0:
            continue
        k = _band(max(effs), step)
        dem[k] = dem.get(k, 0) + b.qty_t
    sup: dict[int, int] = {}
    for a in bk.asks:
        k = _band(a.min_price_t, step)
        sup[k] = sup.get(k, 0) + a.qty_t

    def bands(d: dict[int, int]) -> list[dict]:
        return [{"price_from": k, "price_to": k + step, "qty_t": q} for k, q in sorted(d.items())]

    return {
        "basket_id": bi.basket_id, **{k: v for k, v in store.basket_public(bi).items() if k != "basket_id"},
        "step": step, "price_basis": "warehouse",
        "bands_demand": bands(dem), "bands_supply": bands(sup),
        "totals": {"bids": len(bk.bids), "bid_t": sum(b.qty_t for b in bk.bids),
                   "asks": len(bk.asks), "ask_t": sum(a.qty_t for a in bk.asks)},
        "closed": closed, "clearing_price_t": price,
    }

def _runs_of(mid: str) -> list[str]:
    return [rid for rid, bk in store.S.run_baskets.items() if any(b.mandate_id == mid for b in bk.bids)]

def mandate_view(mid: str) -> dict:
    m = store.S.mandates[mid]
    runs = _runs_of(mid)
    parts = []
    reason = hint = None
    price = None
    for rid in runs:
        res = store.S.runs[rid]
        for a in res.allocations:
            if a.mandate_id == mid:
                parts.append({"run_id": rid, "seller": a.seller, "qty_t": a.qty_t, "price_t": a.price_t,
                              "tariff_t": a.tariff_t, "delivered_price_t": a.delivered_price_t})
                price = a.price_t
        for u in res.unfilled:
            if u.mandate_id == mid:
                reason, hint = u.reason, u.fill_at_max_price_t
    filled = sum(p["qty_t"] for p in parts)
    remaining = store.S.remaining[mid]
    bid_ = store.mandate_basket(mid)
    bi = store.S.baskets.get(bid_) if bid_ else None
    if remaining <= 0:
        status = "filled"
    elif filled > 0:
        status = "partial"
    elif bi is not None and m.expiry < bi.window_end:
        status = "expired"
    elif runs:
        status = "unfilled"
    else:
        status = "in_basket"
    last_run = runs[-1] if runs else None
    avg = round(sum(p["qty_t"] * p["delivered_price_t"] for p in parts) / filled) if filled else None
    return {
        "mandate_id": mid, "status": status, "commodity": m.line_items[0].commodity, "grade": m.line_items[0].grade,
        "qty_t": m.qty_t, "filled_t": filled, "remaining_t": max(remaining, 0), "region": m.region,
        "max_price_t": m.max_price_t, "deadline": m.execution_window.not_after.isoformat(),
        "created_at": m.created_at.isoformat(timespec="seconds"), "phrase": m.natural_language_description,
        "basket_id": bid_, "basket": store.basket_public(bi) if bi else None,
        "run_id": last_run, "deal_id": f"{last_run}:{mid}" if last_run and filled else None,
        "clearing_price_t": price, "delivered_price_t": avg, "sellers": sorted({p["seller"] for p in parts}),
        "parts": parts, "reason": None if status == "filled" else reason, "fill_at_max_price_t": hint,
        "hash": store.S.hashes.get(mid), "principal_kind": m.principal.kind,
    }

def mine(principal_id: str) -> list[dict]:
    with store.LOCK:
        ids = [mid for mid, m in store.S.mandates.items() if m.principal.key() == principal_id]
        return sorted((mandate_view(mid) for mid in ids), key=lambda v: v["created_at"], reverse=True)

PAST_WINDOWS = [("2026-11-05", "16:30", "16:50"), ("2026-11-06", "11:30", "11:50"), ("2026-11-06", "16:30", "16:50")]

@lru_cache(maxsize=1)
def demo_past_runs() -> list[dict]:
    from ..clearing.engine import run
    from ..demo.scenario import scenario
    from ..clearing.models import Ask
    sc = scenario()
    asks = [Ask(**{k: v for k, v in a.items() if k in Ask.model_fields}) for a in sc["asks"]]
    regions = sorted({b["region"] for b in sc["buyers"]})
    out = []
    for i, (day, a, b) in enumerate(PAST_WINDOWS):
        t0 = dt.datetime.fromisoformat(f"{day}T09:00:00")
        for attempt in range(50):
            rnd = random.Random(config.DEMO_SEED * 100 + i * 50 + attempt)
            bids = [Bid(mandate_id=f"P{i}-{j:02d}", qty_t=rnd.choice([5, 10, 15, 20, 30, 40, 60, 100, 150]),
                        max_price_t=rnd.randrange(460_000, 640_001, 10_000), region=rnd.choice(regions),
                        created_at=t0 + dt.timedelta(minutes=7 * j)) for j in range(rnd.randint(5, 9))]
            bk = Basket(basket_id=f"B-cement-32.5-{day.replace('-', '')}-{a.replace(':', '')}", bids=bids,
                        asks=asks, close_time=dt.datetime.fromisoformat(f"{day}T{b}:00"))
            res = run(bk, demo_tariff())
            if res.executed_qty_t > 0:
                break
        out.append({"run_id": res.run_id, "basket_id": bk.basket_id, "date": day, "window": f"{a}–{b}",
                    "clearing_price_t": res.clearing_price_t, "executed_qty_t": res.executed_qty_t,
                    "n_bids": res.aggregates.n_bids, "n_asks": res.aggregates.n_asks,
                    "tie_break_used": res.tie_break_used, "demo": True,
                    "demo_note": "демо-корзина: покупатели вымышленные, заводы и их цены — из сделок UZEX"})
    return out

def history(commodity: str = "cement", grade: str = "32.5") -> list[dict]:
    rows = []
    with store.LOCK:
        for bi in store.S.baskets.values():
            if bi.commodity != commodity or bi.grade != grade or bi.status != "closed" or not bi.run_id:
                continue
            res = store.S.runs[bi.run_id]
            rows.append({"run_id": res.run_id, "basket_id": bi.basket_id, "date": bi.window_start.date().isoformat(),
                         "window": f"{bi.window_start:%H:%M}–{bi.window_end:%H:%M}",
                         "clearing_price_t": res.clearing_price_t, "executed_qty_t": res.executed_qty_t,
                         "n_bids": res.aggregates.n_bids, "n_asks": res.aggregates.n_asks,
                         "tie_break_used": res.tie_break_used, "demo": False,
                         "closed_at": store.S.closed_at.get(bi.basket_id)})
    if commodity == "cement" and grade == "32.5":
        rows += demo_past_runs()
    return sorted(rows, key=lambda r: (r["date"], r["window"], r.get("closed_at") or ""), reverse=True)
