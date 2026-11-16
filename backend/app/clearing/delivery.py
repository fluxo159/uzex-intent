from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

Tariff = dict[tuple[str, str], int]

_TARIFF_FILE = Path(__file__).resolve().parents[3] / "data" / "demo" / "delivery_tariff.json"

def tariff_t(table: Tariff | None, src: str, dst: str) -> int | None:
    if src == dst:
        return 0
    if table is None:
        return None
    v = table.get((src, dst))
    if v is None:
        v = table.get((dst, src))
    return None if v is None else int(v)

def from_json(obj: dict) -> Tariff:
    return {(r["from"], r["to"]): int(r["t"]) for r in obj["rows"]}

@lru_cache(maxsize=1)
def demo_tariff() -> Tariff:
    return from_json(json.loads(_TARIFF_FILE.read_text(encoding="utf-8")))

def zero_tariff(regions) -> Tariff:
    regions = list(regions)
    return {(a, b): 0 for a in regions for b in regions}
