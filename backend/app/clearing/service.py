from __future__ import annotations

import json

from .. import config
from ..book import store
from .delivery import demo_tariff
from .engine import run
from .models import ClearingResult

def reference_price(grade: str) -> int | None:
    try:
        from ..market import chart
        h = chart.history_7d(chart.hist_df(), grade)
        return int(h["vwap"]) if h else None
    except Exception:
        return None

def log_run(result: ClearingResult, basket) -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": result.run_id, "engine_version": result.engine_version,
               "input": basket.model_dump(mode="json"), "output": result.model_dump(mode="json")}
    (config.LOG_DIR / f"{result.run_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")

def close_basket(basket_id: str) -> ClearingResult:
    with store.LOCK:
        return _close_basket(basket_id)

def _close_basket(basket_id: str) -> ClearingResult:
    bi = store.S.baskets.get(basket_id)
    if bi is None:
        raise KeyError(basket_id)
    if bi.status == "closed" and bi.run_id:
        return store.S.runs[bi.run_id]
    basket = store.get_basket(basket_id)
    tariff = demo_tariff()
    result = run(basket, tariff, reference_price(basket.grade))
    try:
        log_run(result, basket)
    except OSError:
        pass
    store.record_run(basket_id, basket, result)
    try:
        from ..audit import sources
        sources.register_run(result, basket, tariff)
    except Exception:
        pass
    return result

def get_result(run_id: str) -> ClearingResult:
    return store.S.runs[run_id]
