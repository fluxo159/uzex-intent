from __future__ import annotations

from collections import defaultdict

from .delivery import Tariff, tariff_t
from .models import Ask, Bid

RawAlloc = tuple[str, str, int, int]

def apply_pooling(allocs: list[RawAlloc], asks: list[Ask], price: int, tariff: Tariff | None,
                  bids: dict[str, Bid]) -> tuple[list[RawAlloc], list[tuple[str, int]]]:
    allocs = list(allocs)
    by_ask = {a.offer_id: a for a in asks}
    failed: list[tuple[str, int]] = []

    def totals() -> dict[str, int]:
        t: dict[str, int] = defaultdict(int)
        for _, oid, q, _ in allocs:
            t[oid] += q
        return t

    for a in asks:
        tot = totals()
        have = tot.get(a.offer_id, 0)
        if have == 0 or have >= a.min_lot_t:
            continue
        group = [x for x in allocs if x[1] == a.offer_id]
        allocs = [x for x in allocs if x[1] != a.offer_id]
        for mid, _, q, _ in group:
            b = bids[mid]
            tot = totals()
            opts = []
            for d in asks:
                if d.offer_id == a.offer_id or d.min_price_t > price:
                    continue
                t = tariff_t(tariff, d.warehouse_region, b.region)
                if t is None or price + t > b.max_price_t:
                    continue
                free = d.qty_t - tot.get(d.offer_id, 0)
                if free < q or tot.get(d.offer_id, 0) + q < d.min_lot_t:
                    continue
                opts.append((t, d.min_price_t, d.created_at, d.offer_id))
            if opts:
                opts.sort()
                allocs.append((mid, opts[0][3], q, opts[0][0]))
            else:
                failed.append((mid, q))
    return allocs, failed
