from __future__ import annotations

from typing import Any

from ..mandate import fees

def required(line_items: list[dict[str, Any]]) -> dict:
    deposit = fee = gross = 0
    for it in line_items:
        c = fees.compute(int(it["qty_t"]), int(it["max_price_t"]))
        deposit += c["deposit_worst"]
        fee += c["exchange_fee"]
        gross += c["gross_max"]
    return {"deposit_worst": deposit, "exchange_fee": fee, "required": deposit + fee, "gross_max": gross}

def check(funds_available: int | None, line_items: list[dict[str, Any]]) -> dict:
    req = required(line_items)
    have = int(funds_available or 0)
    short = max(0, req["required"] - have)
    passed = have >= req["required"]
    fmt = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731
    return {
        "name": "funds", "passed": passed, "level": "ok" if passed else "blocked",
        "reason": (f"на счёте {fmt(have)} сум ≥ задаток {fmt(req['deposit_worst'])} + сбор {fmt(req['exchange_fee'])}"
                   if passed else f"не хватает {fmt(short)} сум; пополните счёт в РКП"),
        "how_to_fix": None if passed else "пополнить счёт в РКП",
        "shortfall": short, "funds_available": have, **req,
    }
