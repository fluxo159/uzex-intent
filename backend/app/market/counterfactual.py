from __future__ import annotations

from ..i18n.uzlatin import to_latin

import json
from pathlib import Path

from .. import config
from .objects import g, items

AI92_FILE = "ai92_2026-11-06.json"
AI92_CAPTION_RU = "если бы те же пять покупателей подали поручения в одну корзину"
AI92_CAPTION_UZ = "агар ўша беш харидор топшириқларни битта саватга берганида"

class CounterfactualError(ValueError):
    pass

def overpay(fills: list[tuple[int, int, int]]) -> dict:
    pay_as_bid = uniform = 0
    for qty, ceiling, paid in fills:
        qty, ceiling, paid = int(qty), int(ceiling), int(paid)
        if qty < 0:
            raise CounterfactualError("отрицательный объём")
        if ceiling < paid:
            raise CounterfactualError(f"потолок {ceiling} ниже цены исполнения {paid} — нарушен I2 движка")
        pay_as_bid += qty * ceiling
        uniform += qty * paid
    return {"pay_as_bid_total": pay_as_bid, "uniform_total": uniform, "overpay": pay_as_bid - uniform,
            "overpay_pct": round(100 * (pay_as_bid - uniform) / uniform, 4) if uniform else 0.0}

def for_basket(result, bids) -> dict:
    if isinstance(bids, dict) and bids and not any(isinstance(v, dict) for v in bids.values()):
        ceilings = {str(k): int(v) for k, v in bids.items()}
    else:
        ceilings = {str(g(b, "mandate_id")): int(g(b, "max_price_t")) for b in (bids or [])}
    fills = []
    for a in items(result, "allocations"):
        mid = str(g(a, "mandate_id"))
        if mid not in ceilings:
            raise CounterfactualError(f"нет заявки для аллокации {mid}")
        paid = g(a, "delivered_price_t")
        if paid is None:
            paid = g(a, "price_t")
        fills.append((int(g(a, "qty_t")), ceilings[mid], int(paid)))
    res = overpay(fills)
    res.update({"clearing_price_t": g(result, "clearing_price_t"), "n_allocations": len(fills),
                "n_buyers": len({str(g(a, "mandate_id")) for a in items(result, "allocations")})})
    return res

def uniform_price(bids: list[tuple[int, int]], asks: list[tuple[int, int]],
                  reference: int | None = None) -> int | None:
    if not bids or not asks:
        return None
    prices = sorted({p for p, _ in bids} | {p for p, _ in asks})

    def dem(p):
        return sum(q for b, q in bids if b >= p)

    def sup(p):
        return sum(q for a, q in asks if a <= p)

    best = max(min(dem(p), sup(p)) for p in prices)
    if best <= 0:
        return None
    cand = [p for p in prices if min(dem(p), sup(p)) == best]
    surplus = min(abs(dem(p) - sup(p)) for p in cand)
    cand = [p for p in cand if abs(dem(p) - sup(p)) == surplus]
    if len(cand) > 1:
        sides = {(dem(p) > sup(p)) - (dem(p) < sup(p)) for p in cand}
        if sides == {1}:
            return max(cand)
        if sides == {-1}:
            return min(cand)
        if reference is not None:
            return min(cand, key=lambda p: (abs(p - reference), p))
        mid = (min(cand) + max(cand)) / 2
        return int(round(mid / 10) * 10)
    return cand[0]

def load_ai92(path: Path | None = None) -> dict:
    path = path or config.DATA_DEMO / AI92_FILE
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _deal_fields(d: dict) -> tuple[int, int]:
    price = d.get("price_t", d.get("price_uzs_per_t", d.get("price")))
    qty = d.get("qty_t", d.get("tonnes", d.get("qty")))
    return int(price), int(qty)

def ai92(data: dict | None = None) -> dict:
    data = data or load_ai92()
    deals = data["deals"]
    bids = [_deal_fields(d) for d in deals]
    total_qty = sum(q for _, q in bids)
    ask_price = min(p for p, _ in bids)
    p_star = uniform_price(bids, [(ask_price, total_qty)])
    res = overpay([(q, p, p_star) for p, q in bids])
    return {
        "commodity": data.get("commodity", "АИ-92"), "date": data.get("date"), "contract": data.get("contract"),
        "seller": data.get("seller"),
        "deals": [{"price_t": p, "qty_t": q, "overpay": q * (p - p_star)} for p, q in bids],
        "prices": [p for p, _ in bids], "n_deals": len(bids), "total_qty_t": total_qty,
        "spread_t": max(p for p, _ in bids) - ask_price,
        "uniform_price_t": p_star, **res,
        "caption_ru": AI92_CAPTION_RU, "caption_uz": to_latin(AI92_CAPTION_UZ),
        "source": data.get("source", "реестр UZEX 06.11.2026"),
        "source_label_ru": "реестр UZEX 06.11.2026, объёмы демо",
        "source_label_uz": to_latin("UZEX реестри 06.11.2026, ҳажмлар демо"),
        "volumes_note": data.get("volumes_note"),
    }
