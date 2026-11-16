import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DEMO_CLOCK", "fixed")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

with TestClient(app) as c:
    c.post("/demo/step/2")
    from app.book import store
    run = list(store.S.runs.values())[-1]
    cf = c.get("/market/counterfactual/ai92").json()
    filled = {a.mandate_id for a in run.allocations}
    out = {
        "basket_price_base_t": run.clearing_price_t, "tie_break": run.tie_break_used,
        "executed_t": run.executed_qty_t, "demand_t": run.aggregates.total_demand, "supply_t": run.aggregates.total_supply,
        "n_buyers": run.aggregates.n_bids, "n_plants": run.aggregates.n_asks, "n_filled": len(filled),
        "delivered_prices_t": sorted({a.delivered_price_t for a in run.allocations}),
        "lots": [{"seller": g.seller, "qty_t": g.qty_t, "n_mandates": g.n_mandates} for g in run.lot_groups],
        "ai92": {k: cf.get(k) for k in ("uniform_price_t", "overpay", "spread_t", "total_qty_t", "pay_as_bid_total",
                                        "uniform_total", "volumes_note")},
        "ai92_prices": [d["price_t"] for d in cf.get("deals", [])],
        "source": "данные UZEX, сделки до 06.11.2026; покупатели вымышленные; объёмы — демо",
    }
    c.post("/demo/reset")
(ROOT / "docs" / "pitch_numbers.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
