from fastapi import APIRouter, HTTPException

from ..audit import sources
from ..market.objects import g, items
from . import flags as fl
from . import graph

router = APIRouter(prefix="/radar", tags=["radar"])

@router.get("/flags/{run_id}")
def get_flags(run_id: str) -> dict:
    data = graph.load_synthetic()
    res = fl.run_flags(data, run_id)
    if res is not None:
        return res
    run = sources.get_run(run_id)
    if run is None:
        raise HTTPException(404, "прогон не найден")
    by_inn = {p["inn"]: p["id"] for p in data.get("participants", [])}
    bids = []
    for b in items(run["basket"], "bids"):
        mid = str(g(b, "mandate_id"))
        pid = by_inn.get(str(sources.mandate_info(mid).get("inn", "")))
        if pid:
            bids.append({"mandate_id": mid, "participant": pid})
    return {"run_id": run_id, "flags": fl.flags(graph.build(data), bids), "n_bids": len(items(run["basket"], "bids")),
            "demo": True, "demo_label": fl.DEMO_LABEL,
            "note": "участники корзины сопоставлены с вымышленным графом по ИНН; несопоставленные флагов не дают"}

@router.get("/graph")
def get_graph() -> dict:
    G = graph.build(graph.load_synthetic())
    return {"nodes": [{"id": n, "name": d.get("name"), "role": d.get("role"), "region": d.get("region"),
                       "node_facts": d.get("node_facts", [])} for n, d in sorted(G.nodes(data=True))],
            "edges": [{"from": u, "to": v, "kind": d["kind"], "fact": d["fact"]} for u, v, d in G.edges(data=True)],
            "demo": True, "demo_label": fl.DEMO_LABEL}
