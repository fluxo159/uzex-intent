from __future__ import annotations

import networkx as nx

from .delivery import Tariff, tariff_t
from .models import Ask, Bid

RawAlloc = tuple[str, str, int, int]

def reroute(allocs: list[RawAlloc], bids: dict[str, Bid], asks: list[Ask], price: int,
            tariff: Tariff | None) -> list[RawAlloc]:
    if not allocs:
        return allocs
    need: dict[str, int] = {}
    for mid, _, q, _ in allocs:
        need[mid] = need.get(mid, 0) + q
    total = sum(need.values())
    k = len(asks) + 1
    rank = {a.offer_id: i for i, a in enumerate(asks)}
    g = nx.DiGraph()
    g.add_node("S", demand=-total)
    g.add_node("T", demand=total)
    for mid in sorted(need):
        g.add_edge("S", f"b:{mid}", capacity=need[mid], weight=0)
    for a in asks:
        if a.min_price_t <= price:
            g.add_edge(f"a:{a.offer_id}", "T", capacity=a.qty_t, weight=0)
    for mid in sorted(need):
        b = bids[mid]
        for a in asks:
            if a.min_price_t > price:
                continue
            t = tariff_t(tariff, a.warehouse_region, b.region)
            if t is None or price + t > b.max_price_t:
                continue
            g.add_edge(f"b:{mid}", f"a:{a.offer_id}", capacity=need[mid], weight=t * k + rank[a.offer_id])
    try:
        flow = nx.min_cost_flow(g)
    except nx.NetworkXUnfeasible:
        return allocs
    out: list[RawAlloc] = []
    for mid in sorted(need):
        b = bids[mid]
        for node, q in sorted(flow.get(f"b:{mid}", {}).items()):
            if q > 0:
                oid = node[2:]
                a = asks[rank[oid]]
                out.append((mid, oid, int(q), int(tariff_t(tariff, a.warehouse_region, b.region))))
    return out
