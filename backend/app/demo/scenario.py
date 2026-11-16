from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache

from .. import config
from ..book import store
from ..clearing.models import Ask
from ..mandate.schema import MandateFields, Principal

@lru_cache(maxsize=1)
def scenario() -> dict:
    return json.loads((config.DATA_DEMO / "scenario_2035.json").read_text(encoding="utf-8"))

def _reset_modules() -> None:
    for mod, fn in (("audit.sources", "reset"), ("escrow.store", "reset")):
        try:
            m = __import__(f"app.{mod}", fromlist=[fn])
            getattr(m, fn)()
        except Exception:
            pass

def load_asks() -> list[str]:
    ids = []
    for a in scenario()["asks"]:
        ask = Ask(**{k: v for k, v in a.items() if k in Ask.model_fields})
        ids.append(store.add_ask(ask, "cement", "32.5", meta={"contract": a.get("contract"), "volume_demo": True}))
    return ids

def buyer_fields(key: str) -> MandateFields:
    e = scenario()["expected_fields"][key]
    return MandateFields(**e)

def buyer_principal(b: dict) -> Principal:
    return Principal(kind=b["kind"], display_name=b["display_name"], region=b["region"], inn=b.get("inn"))

SKIPPED: list[dict] = []

def load_buyers() -> list[str]:
    from ..mandate import service
    ids = []
    SKIPPED.clear()
    for b in scenario()["buyers"]:
        at = dt.datetime.fromisoformat(b["created_at"])
        fa = b.get("funds_available")
        p = service.preview(buyer_fields(b["key"]), buyer_principal(b), b["phrase"], b["lang"], fa, now=at)
        if p.mandate_draft is None:
            SKIPPED.append({"key": b["key"], "errors": [e.code for e in p.errors]})
            continue
        ids.append(service.sign(p.mandate_draft, fa)["mandate_id"])
    return ids

def reset(step: int = 1) -> dict:
    with store.LOCK:
        return _reset(step)

def _reset(step: int) -> dict:
    store.reset()
    _reset_modules()
    store.open_basket()
    out: dict = {"step": step, "asks": load_asks(), "buyers": []}
    if step >= 1:
        out["buyers"] = load_buyers()
        out["skipped"] = list(SKIPPED)
    out["basket_id"] = store.open_basket_id()
    if step >= 2:
        from ..clearing import service as cs
        r = cs.close_basket(out["basket_id"])
        out["run_id"] = r.run_id
        out["closed_basket_id"] = out["basket_id"]
        out["basket_id"] = store.open_basket_id()
    return out
