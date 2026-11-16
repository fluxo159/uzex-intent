from __future__ import annotations

import datetime as dt
from typing import Any

from .. import config
from ..market import calendar as cal
from ..market import chart
from ..market.objects import g, items
from . import card

def _history(basket: Any) -> dict | None:
    grade = g(basket, "grade", "32.5") or "32.5"
    try:
        return chart.history_7d(chart.hist_df(), chart.normalize_grade_param(str(grade)),
                                dt.date.fromisoformat(config.DATA_CUTOFF))
    except Exception:  # noqa: BLE001 — нет истории → нет строки «к прошлой неделе»
        return None

def next_window_label(now: str | None = None, lang: str = "ru") -> str | None:
    wins = cal.next_windows(now, 2)
    if not wins:
        return None
    now_dt = cal.parse_now(now)
    w = next((x for x in wins if not x["is_open_now"]), wins[0])
    start = dt.datetime.fromisoformat(w["start"])
    hm = start.strftime("%H:%M")
    delta = (start.date() - now_dt.date()).days
    if delta == 0:
        return ("сегодня " if lang == "ru" else "бугун ") + hm
    if delta == 1:
        return ("завтра " if lang == "ru" else "эртага ") + hm
    return start.strftime("%d.%m ") + hm

def explain_run(run: dict, mandate_id: str, lang: str | None = None, history: dict | None = None,
                rephrase=None) -> dict:
    basket = run["basket"]
    hist = history if history is not None else _history(basket)
    lang = lang if lang in ("ru", "uz") else "ru"
    out = card.build(run["result"], basket, mandate_id, lang, hist, run.get("tariff"),
                     {"ru": next_window_label(lang="ru"), "uz": next_window_label(lang="uz")}, rephrase)
    out.update(deal_fields(run["result"], mandate_id))
    return out

def deal_fields(result: Any, mandate_id: str) -> dict:
    mine = [a for a in items(result, "allocations") if str(g(a, "mandate_id")) == str(mandate_id)]
    if not mine:
        return {"seller": None, "delivery_t": None, "deal_id": None, "parts": []}
    parts = [{"seller": g(a, "seller"), "qty_t": int(g(a, "qty_t")), "delivery_t": int(g(a, "tariff_t", 0) or 0),
              "delivered_price_t": int(g(a, "delivered_price_t", g(a, "price_t")))} for a in mine]
    main = max(parts, key=lambda p: (p["qty_t"], -p["delivery_t"]))
    sellers = []
    for p in parts:
        if p["seller"] not in sellers:
            sellers.append(p["seller"])
    return {"seller": " + ".join(str(x) for x in sellers), "delivery_t": main["delivery_t"],
            "deal_id": f"{g(result, 'run_id')}:{mandate_id}", "parts": parts}
