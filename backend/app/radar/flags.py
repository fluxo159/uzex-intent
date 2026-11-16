from __future__ import annotations

from itertools import combinations

import networkx as nx

from .graph import build, component_of

APPEAL_TEXT = "ответ в 10 дней (ЗПД ст. 24)"
DEMO_LABEL = "ДЕМО: участники вымышленные"

def _edges_on_path(G: nx.MultiGraph, path: list[str]) -> list[dict]:
    out = []
    for u, v in zip(path, path[1:]):
        for _, data in sorted(G.get_edge_data(u, v).items()):
            out.append({"from": u, "to": v, "kind": data["kind"], "fact": data["fact"]})
    return out

def flags(G: nx.MultiGraph, bids: list[dict]) -> list[dict]:
    comp = component_of(G)
    groups: dict[int, list[dict]] = {}
    for b in bids:
        pid = b.get("participant")
        if pid in comp and G.degree(pid) > 0:
            groups.setdefault(comp[pid], []).append(b)
    out = []
    for cid, bs in sorted(groups.items()):
        members = sorted({b["participant"] for b in bs})
        if len(bs) < 2:
            continue
        edges, seen = [], set()
        for a, b in combinations(members, 2):
            for e in _edges_on_path(G, nx.shortest_path(G, a, b)):
                key = (min(e["from"], e["to"]), max(e["from"], e["to"]), e["kind"])
                if key not in seen:
                    seen.add(key)
                    edges.append(e)
        if len(members) == 1:
            edges = []
        node_facts = {m: G.nodes[m].get("node_facts", []) for m in members if G.nodes[m].get("node_facts")}
        out.append({
            "flag_id": f"F{len(out) + 1}", "component": cid,
            "mandate_ids": sorted(b["mandate_id"] for b in bs),
            "participants": [{"id": m, "name": G.nodes[m].get("name", m), "inn": G.nodes[m].get("inn")} for m in members],
            "edges": edges, "node_facts": node_facts,
            "summary": f"{len(bs)} заявки в одной корзине от связанных участников",
            "appeal": APPEAL_TEXT, "scoring": None,
        })
    return out

def run_flags(data: dict, run_id: str) -> dict | None:
    basket = next((b for b in data.get("baskets", []) if b["run_id"] == run_id), None)
    if basket is None:
        return None
    G = build(data)
    return {"run_id": run_id, "flags": flags(G, basket["bids"]), "n_bids": len(basket["bids"]),
            "demo": True, "demo_label": DEMO_LABEL, "note": basket.get("note")}
