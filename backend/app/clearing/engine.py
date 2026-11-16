from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from .. import config
from .delivery import Tariff, tariff_t
from .models import (Aggregates, Allocation, Ask, AskUnfilled, Basket, Bid, ClearingResult,
                     LotGroup, Unfilled)
from .pooling import apply_pooling
from .routing import reroute
from .tiebreak import choose_price

__all__ = ["run", "Basket", "Bid", "Ask", "Allocation", "ClearingResult", "inputs_hash"]

def _bid_key(b: Bid):
    return (b.created_at, b.mandate_id)

def _ask_key(a: Ask):
    return (a.min_price_t, a.created_at, a.offer_id)

def inputs_hash(basket: Basket, tariff: Tariff | None, reference: int | None) -> str:
    bids = sorted((b.model_dump(mode="json") for b in basket.bids), key=lambda x: (x["mandate_id"], x["created_at"]))
    asks = sorted((a.model_dump(mode="json") for a in basket.asks), key=lambda x: (x["offer_id"], x["created_at"]))
    pairs = sorted({(a["warehouse_region"], b["region"]) for a in asks for b in bids})
    used = [[s, d, tariff_t(tariff, s, d)] for s, d in pairs]
    payload = {
        "basket_id": basket.basket_id, "commodity": basket.commodity, "grade": basket.grade,
        "bids": bids, "asks": asks, "tariff": used, "reference": reference,
        "engine_version": config.ENGINE_VERSION,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def run(basket: Basket, tariff: Tariff | None = None, reference_price: int | None = None) -> ClearingResult:
    h = inputs_hash(basket, tariff, reference_price)
    run_id = "R-" + h[:10]
    asks = sorted(basket.asks, key=_ask_key)

    best_eff: dict[str, int | None] = {}
    for b in basket.bids:
        effs = [b.max_price_t - t for a in asks if (t := tariff_t(tariff, a.warehouse_region, b.region)) is not None]
        best_eff[b.mandate_id] = max(effs) if effs else None
    bids = sorted(basket.bids, key=lambda b: (-(best_eff[b.mandate_id] if best_eff[b.mandate_id] is not None else -1),) + _bid_key(b))

    cands = sorted({e for e in best_eff.values() if e is not None and e > 0} | {a.min_price_t for a in asks if a.min_price_t > 0})

    def demand(p: int) -> int:
        return sum(b.qty_t for b in bids if best_eff[b.mandate_id] is not None and best_eff[b.mandate_id] >= p)

    def supply(p: int) -> int:
        return sum(a.qty_t for a in asks if a.min_price_t <= p)

    table = [(p, demand(p), supply(p)) for p in cands]
    best_bid = max((e for e in best_eff.values() if e is not None), default=None)
    best_ask = min((a.min_price_t for a in asks), default=None)
    total_demand = sum(b.qty_t for b in bids)
    total_supply = sum(a.qty_t for a in asks)

    price, rule = choose_price(table, reference_price)

    allocations: list[Allocation] = []
    unfilled: list[Unfilled] = []
    asks_unfilled: list[AskUnfilled] = []

    if price is None:
        for b in bids:
            reason = "no_supply" if not asks else "price_below_clearing"
            unfilled.append(Unfilled(mandate_id=b.mandate_id, qty_t=b.qty_t, reason=reason))
        for a in asks:
            asks_unfilled.append(AskUnfilled(offer_id=a.offer_id, qty_t=a.qty_t, reason="no_demand"))
        marginal = "none"
    else:
        remaining = {a.offer_id: (a.qty_t if a.min_price_t <= price else 0) for a in asks}
        ask_by_id = {a.offer_id: a for a in asks}
        raw_alloc: list[tuple[str, str, int, int]] = []
        for b in bids:
            e = best_eff[b.mandate_id]
            if e is None or e < price:
                unfilled.append(Unfilled(mandate_id=b.mandate_id, qty_t=b.qty_t, reason="price_below_clearing"))
                continue
            opts = []
            for a in asks:
                t = tariff_t(tariff, a.warehouse_region, b.region)
                if t is None or a.min_price_t > price or price + t > b.max_price_t:
                    continue
                opts.append((t,) + _ask_key(a) + (a.offer_id,))
            opts.sort()
            need = b.qty_t
            for o in opts:
                if need == 0:
                    break
                oid = o[-1]
                take = min(need, remaining[oid])
                if take > 0:
                    remaining[oid] -= take
                    need -= take
                    raw_alloc.append((b.mandate_id, oid, take, o[0]))
            if need > 0:
                unfilled.append(Unfilled(mandate_id=b.mandate_id, qty_t=need, reason="no_supply"))

        bid_by_id = {b.mandate_id: b for b in bids}
        raw_alloc = reroute(raw_alloc, bid_by_id, asks, price, tariff)
        pre_pool = {oid for _, oid, _, _ in raw_alloc}
        raw_alloc, lot_fail = apply_pooling(raw_alloc, asks, price, tariff, bid_by_id)
        for mid, q in lot_fail:
            unfilled.append(Unfilled(mandate_id=mid, qty_t=q, reason="lot_not_formed"))

        sold = defaultdict(int)
        for mid, oid, q, t in raw_alloc:
            a = ask_by_id[oid]
            sold[oid] += q
            allocations.append(Allocation(mandate_id=mid, offer_id=oid, seller=a.seller, qty_t=q, price_t=price,
                                          tariff_t=t, delivered_price_t=price + t, lot_group_id=f"LOT-{oid}"))
        lot_failed_asks = {oid for oid in {o for _, o, _, _ in raw_alloc}}
        for a in asks:
            left = a.qty_t - sold[a.offer_id]
            if left <= 0:
                continue
            if a.min_price_t > price:
                reason = "price_above_clearing"
            elif a.offer_id in pre_pool and sold[a.offer_id] == 0:
                reason = "lot_not_formed"
            else:
                reason = "no_demand"
            asks_unfilled.append(AskUnfilled(offer_id=a.offer_id, qty_t=left, reason=reason))
        d, s = demand(price), supply(price)
        marginal = "demand" if d > s else "supply" if s > d else "balanced"

    unfilled = _merge_unfilled(unfilled)
    for u in unfilled:
        if u.reason == "price_below_clearing":
            u.fill_at_max_price_t = _fill_hint(next(b for b in bids if b.mandate_id == u.mandate_id), asks, price, tariff)
    allocations.sort(key=lambda x: (x.offer_id, x.mandate_id))
    executed = sum(x.qty_t for x in allocations)

    groups: dict[str, LotGroup] = {}
    bid_region = {b.mandate_id: b.region for b in bids}
    ask_by_id = {a.offer_id: a for a in asks}
    for al in allocations:
        g = groups.get(al.lot_group_id)
        if g is None:
            a = ask_by_id[al.offer_id]
            g = groups[al.lot_group_id] = LotGroup(lot_group_id=al.lot_group_id, offer_id=a.offer_id, seller=a.seller,
                                                   qty_t=0, n_mandates=0, min_lot_t=a.min_lot_t, regions={})
        g.qty_t += al.qty_t
        g.n_mandates += 1
        r = bid_region[al.mandate_id]
        g.regions[r] = g.regions.get(r, 0) + al.qty_t

    agg = Aggregates(
        demand_curve=[(p, d) for p, d, _ in table], supply_curve=[(p, s) for p, _, s in table],
        total_demand=total_demand, total_supply=total_supply, n_bids=len(bids), n_asks=len(asks),
        n_executed_bids=len({x.mandate_id for x in allocations}),
        n_executed_asks=len({x.offer_id for x in allocations}),
        marginal_side=marginal, best_bid=best_bid, best_ask=best_ask,
    )
    return ClearingResult(
        run_id=run_id, basket_id=basket.basket_id, engine_version=config.ENGINE_VERSION,
        clearing_price_t=price, executed_qty_t=executed, allocations=allocations,
        unfilled=unfilled, asks_unfilled=sorted(asks_unfilled, key=lambda x: (x.offer_id, x.reason)),
        aggregates=agg, tie_break_used=rule, lot_groups=sorted(groups.values(), key=lambda g: g.lot_group_id),
        reference_price_t=reference_price, inputs_hash=h,
    )

def _merge_unfilled(items: list[Unfilled]) -> list[Unfilled]:
    acc: dict[tuple[str, str], int] = defaultdict(int)
    for u in items:
        acc[(u.mandate_id, u.reason)] += u.qty_t
    return [Unfilled(mandate_id=m, qty_t=q, reason=r) for (m, r), q in sorted(acc.items()) if q > 0]

def _fill_hint(b: Bid, asks: list[Ask], price: int | None, tariff: Tariff | None) -> int | None:
    opts = []
    for a in asks:
        t = tariff_t(tariff, a.warehouse_region, b.region)
        if t is None:
            continue
        base = max(price, a.min_price_t) if price is not None else a.min_price_t
        opts.append(base + t)
    return min(opts) if opts else None

def outcome_for(result: ClearingResult, mandate_id: str, qty_t: int) -> str:
    got = sum(a.qty_t for a in result.allocations if a.mandate_id == mandate_id)
    if got == 0:
        return "unfilled"
    return "filled" if got >= qty_t else "partial"
