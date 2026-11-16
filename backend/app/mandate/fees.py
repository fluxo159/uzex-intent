from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .. import config

def round_half_up(x) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def gross_max(qty_t: int, max_price_t: int) -> int:
    return int(qty_t) * int(max_price_t)

def exchange_fee(gross: int, rate: float = config.BUYER_FEE_RATE) -> int:
    return round_half_up(Decimal(int(gross)) * Decimal(str(rate)))

def deposit(gross: int, rate: float = config.DEPOSIT_WORST) -> int:
    return round_half_up(Decimal(int(gross)) * Decimal(str(rate)))

def compute(qty_t: int, max_price_t: int, delivery_range: tuple[int, int] | None = None,
            deposit_rate: float | None = None) -> dict:
    if int(qty_t) < 1:
        raise ValueError("количество должно быть не меньше 1 тонны")
    if int(max_price_t) < 1:
        raise ValueError("цена должна быть больше нуля")
    g = gross_max(qty_t, max_price_t)
    fee = exchange_fee(g)
    rate = config.DEPOSIT_WORST if deposit_rate is None else deposit_rate
    dep = deposit(g, rate)
    dmin, dmax = delivery_range if delivery_range else (0, 0)
    return {
        "gross_max": g,
        "fee_rate": config.BUYER_FEE_RATE,
        "exchange_fee": fee,
        "deposit_rate": rate,
        "deposit_worst": dep,
        "deposit_final": deposit_rate is not None,
        "delivery_min_t": int(dmin),
        "delivery_max_t": int(dmax),
        "total_worst": g + fee,
        "needed_now": dep + fee,
    }
