from __future__ import annotations

from ..book import store
from ..clearing.delivery import demo_tariff, tariff_t

def find_offer(seller: str) -> str | None:
    s = seller.strip().lower()
    for oid, a in store.S.plants.items():
        if oid.lower() == s or a.seller.lower() == s:
            return oid
    for rid in reversed(list(store.S.runs)):
        for a in store.S.run_baskets[rid].asks:
            if a.offer_id.lower() == s or a.seller.lower() == s:
                return a.offer_id
    return None

def _ask(oid: str):
    if oid in store.S.asks:
        return store.S.asks[oid]
    if oid in store.S.plants:
        return store.S.plants[oid].model_copy(update={"qty_t": 1})
    for rid in reversed(list(store.S.runs)):
        for a in store.S.run_baskets[rid].asks:
            if a.offer_id == oid:
                return a
    return None

def demand(seller: str) -> dict:
    oid = find_offer(seller)
    if oid is None:
        raise KeyError(seller)
    ask = _ask(oid)
    tar = demo_tariff()
    bid_ = store.open_basket_id()
    bk = store.get_basket(bid_)
    regions: dict[str, dict] = {}
    total_t = 0
    for b in bk.bids:
        total_t += b.qty_t
        t = tariff_t(tar, ask.warehouse_region, b.region)
        if t is None or b.max_price_t - t < ask.min_price_t:
            continue
        m = store.S.mandates[b.mandate_id]
        r = regions.setdefault(b.region, {"region": b.region, "qty_t": 0, "n_mandates": 0, "largest_t": 0,
                                          "earliest_deadline": None, "tariff_t": t, "sizes": []})
        r["qty_t"] += b.qty_t
        r["n_mandates"] += 1
        r["largest_t"] = max(r["largest_t"], b.qty_t)
        r["sizes"].append(b.qty_t)
        d = m.execution_window.not_after.isoformat()
        r["earliest_deadline"] = min(filter(None, [r["earliest_deadline"], d]))
    lot = max(ask.min_lot_t, 1)
    rows = []
    for r in sorted(regions.values(), key=lambda x: (-x["qty_t"], x["region"])):
        r["sizes"].sort(reverse=True)
        r["lots"] = r["qty_t"] // lot
        r["remainder_t"] = r["qty_t"] % lot
        r["rest_t"] = r["remainder_t"]
        r["deadline"] = r["earliest_deadline"]
        rows.append(r)
    ready = sum(r["qty_t"] for r in rows)
    last = None
    for rid in reversed(list(store.S.runs)):
        res = store.S.runs[rid]
        groups = [g.model_dump() for g in res.lot_groups if g.offer_id == oid]
        if any(a.offer_id == oid for a in store.S.run_baskets[rid].asks):
            last = {"run_id": rid, "clearing_price_t": res.clearing_price_t, "lot_groups": groups,
                    "sold_t": sum(g["qty_t"] for g in groups)}
            break
    return {"seller": ask.seller, "offer_id": oid, "warehouse_region": ask.warehouse_region,
            "price_t": ask.min_price_t, "qty_t": store.S.asks[oid].qty_t if oid in store.S.asks else 0, "min_lot_t": ask.min_lot_t, "basket_id": bid_,
            "regions": rows, "ready_at_your_price_t": ready, "basket_demand_t": total_t,
            "buy_at_price_t": ready, "basket_total_t": total_t,
            "sellers": [p.seller for p in store.S.plants.values()],
            "last_run": last, "volume_demo": True, "tariff_demo": True}
