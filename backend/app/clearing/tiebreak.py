from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

def round10(x: Decimal) -> int:
    return int((x / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) * 10

def choose_price(table: list[tuple[int, int, int]], reference: int | None) -> tuple[int | None, str]:
    if not table:
        return None, "none"
    vols = {p: min(d, s) for p, d, s in table}
    vmax = max(vols.values())
    if vmax <= 0:
        return None, "none"
    c1 = [(p, d, s) for p, d, s in table if vols[p] == vmax]
    if len(c1) == 1:
        return c1[0][0], "max_volume"
    smin = min(abs(d - s) for _, d, s in c1)
    c2 = [(p, d, s) for p, d, s in c1 if abs(d - s) == smin]
    if len(c2) == 1:
        return c2[0][0], "min_surplus"
    if all(d > s for _, d, s in c2):
        return max(p for p, _, _ in c2), "market_pressure"
    if all(s > d for _, d, s in c2):
        return min(p for p, _, _ in c2), "market_pressure"
    lo = min(p for p, _, _ in c2)
    hi = max(p for p, _, _ in c2)
    if reference is not None:
        return max(lo, min(hi, int(reference))), "reference"
    mid = round10((Decimal(lo) + Decimal(hi)) / 2)
    return max(lo, min(hi, mid)), "midpoint"
