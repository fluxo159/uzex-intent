from __future__ import annotations

from typing import Any, Callable

from ..market.objects import g, items
from ..regions import OBLAST_NAMES

REASONS = ("price_below_clearing", "no_supply", "lot_not_formed")

def fmt(n: int | float | None) -> str:
    if n is None:
        return "—"
    return f"{int(round(n)):,}".replace(",", " ")

def fmt_pct(x: float) -> str:
    s = f"{abs(x):.1f}".replace(".", ",")
    return ("+" if x > 0 else "−" if x < 0 else "") + s + "%"

def tariff_of(tariff: Any, src: str | None, dst: str | None) -> int | None:
    if src is None or dst is None:
        return None
    if src == dst:
        return 0
    if tariff is None:
        return None
    if callable(tariff):
        v = tariff(src, dst)
        return None if v is None else int(v)
    for key in ((src, dst), (dst, src), f"{src}->{dst}", f"{src}|{dst}"):
        if key in tariff:
            return int(tariff[key])
    inner = tariff.get(src) if isinstance(tariff, dict) else None
    if isinstance(inner, dict) and dst in inner:
        return int(inner[dst])
    return None

def _find_bid(basket: Any, mandate_id: str) -> Any:
    for b in items(basket, "bids"):
        if str(g(b, "mandate_id")) == str(mandate_id):
            return b
    return None

def _asks_by_id(basket: Any) -> dict[str, Any]:
    return {str(g(a, "offer_id")): a for a in items(basket, "asks")}

def facts(result: Any, basket: Any, mandate_id: str, history: dict | None = None,
          tariff: Any = None, next_window: str | None = None) -> dict:
    bid = _find_bid(basket, mandate_id)
    if bid is None:
        raise KeyError(f"поручение {mandate_id} не найдено в корзине")
    your_qty = int(g(bid, "qty_t"))
    your_max = int(g(bid, "max_price_t"))
    your_region = g(bid, "region")
    asks = _asks_by_id(basket)
    agg = g(result, "aggregates", {}) or {}
    p_star = g(result, "clearing_price_t")

    mine = [a for a in items(result, "allocations") if str(g(a, "mandate_id")) == str(mandate_id)]
    filled_qty = sum(int(g(a, "qty_t")) for a in mine)
    unf = [u for u in items(result, "unfilled") if str(g(u, "mandate_id")) == str(mandate_id)]
    reason = g(unf[0], "reason") if unf else None

    if filled_qty >= your_qty and filled_qty > 0:
        outcome = "filled"
    elif filled_qty > 0:
        outcome = "partial"
    else:
        outcome = "unfilled"

    delivered = None
    plants: list[dict] = []
    if mine:
        delivered = round(sum(int(g(a, "qty_t")) * int(g(a, "delivered_price_t", g(a, "price_t")))
                              for a in mine) / filled_qty)
        for a in mine:
            ask = asks.get(str(g(a, "offer_id")))
            wh = g(ask, "warehouse_region") if ask is not None else None
            plants.append({"region": wh, "qty_t": int(g(a, "qty_t")),
                           "delivery_t": int(g(a, "tariff_t", None) if g(a, "tariff_t", None) is not None else
                                             int(g(a, "delivered_price_t", g(a, "price_t"))) - int(g(a, "price_t"))),
                           "delivered_price_t": int(g(a, "delivered_price_t", g(a, "price_t")))})

    needed_delivered = None
    if outcome == "unfilled" and p_star is not None:
        best = None
        for a in asks.values():
            if g(a, "min_price_t") is not None and int(g(a, "min_price_t")) <= int(p_star):
                t = tariff_of(tariff, g(a, "warehouse_region"), your_region)
                if t is not None and (best is None or t < best):
                    best = t
        needed_delivered = int(p_star) + best if best is not None else int(p_star)
        if unf and g(unf[0], "fill_at_max_price_t") is not None:
            needed_delivered = int(g(unf[0], "fill_at_max_price_t"))

    supply_from = None
    if p_star is None:
        mins = [int(g(a, "min_price_t")) for a in asks.values() if g(a, "min_price_t") is not None]
        supply_from = min(mins) if mins else None

    lot_collected = lot_needed = None
    if reason == "lot_not_formed":
        lot_collected = g(unf[0], "lot_collected_t")
        lot_needed = g(unf[0], "lot_needed_t")
        if lot_collected is None:
            lot_collected = sum(int(g(u, "qty_t")) for u in items(result, "unfilled")
                                if g(u, "reason") == "lot_not_formed")
        if lot_needed is None:
            lots = [int(g(a, "min_lot_t")) for a in asks.values() if g(a, "min_lot_t")]
            lot_needed = min(lots) if lots else None

    vs_last_week = None
    if history and history.get("vwap") and p_star is not None:
        vs_last_week = 100.0 * (int(p_star) - int(history["vwap"])) / int(history["vwap"])

    return {
        "outcome": outcome, "reason": reason,
        "your_qty": your_qty, "your_filled_qty": filled_qty, "your_rest_qty": your_qty - filled_qty,
        "your_max": your_max, "your_price_delivered": delivered,
        "clearing_price_base": None if p_star is None else int(p_star),
        "needed_delivered": needed_delivered, "supply_from": supply_from,
        "total_demand_t": agg.get("total_demand") if isinstance(agg, dict) else g(agg, "total_demand"),
        "total_supply_t": agg.get("total_supply") if isinstance(agg, dict) else g(agg, "total_supply"),
        "n_buyers": (agg.get("n_bids") if isinstance(agg, dict) else g(agg, "n_bids")) or len(items(basket, "bids")),
        "n_plants": (agg.get("n_asks") if isinstance(agg, dict) else g(agg, "n_asks")) or len(asks),
        "plants": plants, "lot_collected_t": lot_collected, "lot_needed_t": lot_needed,
        "vs_last_week_pct": None if vs_last_week is None else round(vs_last_week, 1),
        "history_vwap": history.get("vwap") if history else None,
        "next_window": next_window,
    }

def _region(code: str | None, lang: str) -> str:
    if not code:
        return "—"
    return OBLAST_NAMES.get(lang, OBLAST_NAMES["ru"]).get(code, code)

def sentences(f: dict, lang: str = "ru") -> dict[str, Any]:
    ru = lang != "uz"
    out: dict[str, Any] = {"why_in": None, "why_out": None, "vs_last_week": None, "plant_region": None,
                           "counterfactual": None}
    s: list[str] = []
    nxt = f.get("next_window")
    if isinstance(nxt, dict):
        nxt = nxt.get(lang) or nxt.get("ru")
    nxt_ru = f"; ближайшая корзина {nxt}" if nxt else ""
    nxt_uz = f"; навбатдаги сават {nxt}" if nxt else ""

    if f["outcome"] in ("filled", "partial"):
        out["why_in"] = (f"ваш потолок {fmt(f['your_max'])} ≥ цена с доставкой {fmt(f['your_price_delivered'])}" if ru else
                         f"сизнинг чегарангиз {fmt(f['your_max'])} ≥ етказиб бериш билан нарх {fmt(f['your_price_delivered'])}")
        if f["outcome"] == "filled":
            s.append(f"Исполнено полностью: {fmt(f['your_qty'])} т по {fmt(f['your_price_delivered'])} сум/т с доставкой." if ru else
                     f"Тўлиқ бажарилди: {fmt(f['your_qty'])} т, етказиб бериш билан {fmt(f['your_price_delivered'])} сўм/т.")
        else:
            s.append(f"Исполнено {fmt(f['your_filled_qty'])} т из {fmt(f['your_qty'])}: в корзине не хватило предложения, "
                     f"ваша заявка — последняя по цене и времени подачи; остаток {fmt(f['your_rest_qty'])} т ждёт следующей корзины."
                     if ru else
                     f"{fmt(f['your_qty'])} т дан {fmt(f['your_filled_qty'])} т бажарилди: саватда таклиф етмади, "
                     f"сизнинг буюртмангиз нарх ва вақт бўйича охирги; қолган {fmt(f['your_rest_qty'])} т кейинги саватни кутади.")
        s.append(("Почему исполнено: " if ru else "Нега бажарилди: ") + out["why_in"] + ".")
    else:
        r = f["reason"]
        if r == "lot_not_formed" and f.get("lot_needed_t"):
            out["why_out"] = (f"набрано {fmt(f['lot_collected_t'])} т из {fmt(f['lot_needed_t'])} нужных заводу, "
                              f"ваше поручение ждёт следующей корзины" + nxt_ru if ru else
                              f"заводга керакли {fmt(f['lot_needed_t'])} т дан {fmt(f['lot_collected_t'])} т йиғилди, "
                              f"топшириғингиз кейинги саватни кутади" + nxt_uz)
        elif f["clearing_price_base"] is None:
            sf = f.get("supply_from")
            out["why_out"] = ((f"в корзине не нашлось сделки: предложение от {fmt(sf)} сум/т на складе, "
                               f"ваш потолок {fmt(f['your_max'])}" if sf is not None else
                               "в корзине не было предложения") + nxt_ru if ru else
                              (f"саватда битим бўлмади: таклиф омборда {fmt(sf)} сўм/т дан, "
                               f"сизнинг чегарангиз {fmt(f['your_max'])}" if sf is not None else
                               "саватда таклиф бўлмади") + nxt_uz)
        else:
            nd = f.get("needed_delivered") or f["clearing_price_base"]
            out["why_out"] = (f"ваш потолок {fmt(f['your_max'])} < цена с доставкой {fmt(nd)}" + nxt_ru if ru else
                              f"сизнинг чегарангиз {fmt(f['your_max'])} < етказиб бериш билан нарх {fmt(nd)}" + nxt_uz)
        s.append(("Не исполнено: " if ru else "Бажарилмади: ") + out["why_out"] + ".")
        s.append("Деньги не списаны, задаток остаётся на вашем счёте до следующей корзины." if ru else
                 "Пул ечилмади, закалат кейинги саватгача ҳисобингизда қолади.")

    if f["clearing_price_base"] is not None:
        s.append(f"Единая цена корзины на складе — {fmt(f['clearing_price_base'])} сум/т для всех "
                 f"{fmt(f['n_buyers'])} покупателей и {fmt(f['n_plants'])} заводов; "
                 f"спрос {fmt(f['total_demand_t'])} т, предложение {fmt(f['total_supply_t'])} т." if ru else
                 f"Саватнинг ягона омбор нархи — {fmt(f['clearing_price_base'])} сўм/т, барча "
                 f"{fmt(f['n_buyers'])} харидор ва {fmt(f['n_plants'])} завод учун; "
                 f"талаб {fmt(f['total_demand_t'])} т, таклиф {fmt(f['total_supply_t'])} т.")

    if f.get("vs_last_week_pct") is not None:
        out["vs_last_week"] = (f"{fmt_pct(f['vs_last_week_pct'])} к средней прошлой недели" if ru else
                               f"ўтган ҳафта ўртачасига нисбатан {fmt_pct(f['vs_last_week_pct'])}")
        s.append(("Цена корзины: " if ru else "Сават нархи: ") + out["vs_last_week"] + ".")

    if f["plants"]:
        parts = []
        for p in f["plants"]:
            parts.append(f"{_region(p['region'], 'ru')}, доставка {fmt(p['delivery_t'])} сум/т (демо-тариф)" if ru else
                         f"{_region(p['region'], 'uz')}, етказиб бериш {fmt(p['delivery_t'])} сўм/т (демо-тариф)")
        out["plant_region"] = "; ".join(parts)
        s.append(("Откуда везут: " if ru else "Қаердан келади: ") + out["plant_region"] + ".")

    if f["clearing_price_base"] is not None:
        out["counterfactual"] = (f"Сегодня каждый платил бы свою ставку и гнался за последней секундой. "
                                 f"Здесь одна цена для всех: {fmt(f['clearing_price_base'])} на складе" if ru else
                                 f"Бугун ҳар ким ўз нархини тўлар ва охирги сонияни қувар эди. "
                                 f"Бу ерда ҳамма учун битта нарх: омборда {fmt(f['clearing_price_base'])}")
        s.append(out["counterfactual"] + ".")
    out["sentences"] = s
    return out

def build(result: Any, basket: Any, mandate_id: str, lang: str | None = None, history: dict | None = None,
          tariff: Any = None, next_window: str | None = None,
          rephrase: Callable[[list[str], str], list[str]] | None = None) -> dict:
    from .guard import guarded_rephrase
    from ..i18n.uzlatin import latinize
    lang = lang if lang in ("ru", "uz") else "ru"
    f = facts(result, basket, mandate_id, history, tariff, next_window)
    ru = sentences(f, "ru")
    uz = latinize(sentences(f, "uz"))
    primary = ru if lang == "ru" else uz
    sent_ru, src_ru = guarded_rephrase(ru["sentences"], "ru", rephrase)
    sent_uz, src_uz = guarded_rephrase(uz["sentences"], "uz", rephrase)
    sent_uz = latinize(sent_uz)
    return {
        "mandate_id": str(mandate_id), "lang": lang, "run_id": g(result, "run_id"),
        "basket_id": g(result, "basket_id"),
        "outcome": f["outcome"], "reason": f["reason"],
        "your_qty": f["your_qty"], "your_filled_qty": f["your_filled_qty"],
        "your_price_delivered": f["your_price_delivered"], "your_max": f["your_max"],
        "clearing_price_base": f["clearing_price_base"],
        "total_demand_t": f["total_demand_t"], "total_supply_t": f["total_supply_t"],
        "n_buyers": f["n_buyers"], "n_plants": f["n_plants"],
        "why_in": primary["why_in"], "why_out": primary["why_out"], "vs_last_week": primary["vs_last_week"],
        "plant_region": primary["plant_region"], "counterfactual": primary["counterfactual"],
        "sentences_ru": sent_ru, "sentences_uz": sent_uz,
        "text_source": {"ru": src_ru, "uz": src_uz},
    }
