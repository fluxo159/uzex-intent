from __future__ import annotations

import json
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import networkx as nx

from .. import config

SYNTHETIC_FILE = "radar_synthetic.json"
BROKER_SHARE_MIN = 0.75
BROKER_MIN_DEALS = 4
PAIR_MIN_DEALS = 5
PAIR_SHARE_MIN = 0.6
FOREIGN_REGION_MIN_DEALS = 3

@lru_cache(maxsize=1)
def load_synthetic(path: str | None = None) -> dict:
    p = Path(path) if path else config.DATA_DEMO / SYNTHETIC_FILE
    return json.loads(p.read_text(encoding="utf-8"))

def _name(parts: dict, pid: str) -> str:
    return parts.get(pid, {}).get("name", pid)

def build(data: dict) -> nx.MultiGraph:
    G = nx.MultiGraph()
    parts = {p["id"]: p for p in data.get("participants", [])}
    for pid, p in parts.items():
        G.add_node(pid, **p, node_facts=[])
    deals = data.get("deals", [])

    by_buyer: dict[str, list[dict]] = defaultdict(list)
    for d in deals:
        by_buyer[d["buyer"]].append(d)
    for a, b in combinations(sorted(by_buyer), 2):
        total = len(by_buyer[a]) + len(by_buyer[b])
        ca = Counter(d["broker"] for d in by_buyer[a])
        cb = Counter(d["broker"] for d in by_buyer[b])
        for broker in sorted(set(ca) & set(cb)):
            via = ca[broker] + cb[broker]
            if via >= BROKER_MIN_DEALS and via >= BROKER_SHARE_MIN * total:
                G.add_edge(a, b, kind="shared_broker", broker=broker, via=via, total=total,
                           fact=f"оба через брокера {broker} в {via} из {total} сделок")

    for buyer, ds in sorted(by_buyer.items()):
        cnt = Counter(d["seller"] for d in ds)
        for seller, k in sorted(cnt.items()):
            if k >= PAIR_MIN_DEALS and k >= PAIR_SHARE_MIN * len(ds):
                G.add_edge(buyer, seller, kind="frequent_pair", deals=k, total=len(ds),
                           fact=f"покупатель {_name(parts, buyer)} и продавец {_name(parts, seller)}: {k} из {len(ds)} сделок покупателя")

    by_addr: dict[str, list[str]] = defaultdict(list)
    for pid, p in parts.items():
        if p.get("warehouse_address"):
            by_addr[p["warehouse_address"]].append(pid)
    for addr, pids in sorted(by_addr.items()):
        for a, b in combinations(sorted(pids), 2):
            G.add_edge(a, b, kind="shared_address", address=addr, fact=f"один адрес склада: {addr}")

    for buyer, ds in by_buyer.items():
        reg = parts.get(buyer, {}).get("region")
        foreign = [d for d in ds if d.get("delivery_region") and d["delivery_region"] != reg]
        if reg and len(foreign) >= FOREIGN_REGION_MIN_DEALS and buyer in G:
            G.nodes[buyer]["node_facts"].append(
                f"{len(foreign)} из {len(ds)} сделок с поставкой не в регион регистрации")
    return G

def component_of(G: nx.MultiGraph) -> dict[str, int]:
    comp = {}
    for i, c in enumerate(sorted((sorted(c) for c in nx.connected_components(G)), key=lambda x: x[0])):
        for n in c:
            comp[n] = i
    return comp
