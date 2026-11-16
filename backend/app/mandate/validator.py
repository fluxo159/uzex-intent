from __future__ import annotations

import re

REFERENCE_NUMBERS = {"32.5", "42.5", "400", "500"}
_NUM_RE = re.compile(r"\d[\d\s   ]*(?:[.,]\d+)?")

def numbers_in(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM_RE.finditer(text or ""):
        raw = m.group(0).strip()
        compact = re.sub(r"[\s   ]", "", raw).replace(",", ".")
        out.add(compact)
        for part in re.split(r"[\s   ]+", raw):
            if part:
                out.add(part.replace(",", "."))
    return {x[:-2] if x.endswith(".0") else x for x in out}

def check(fields: dict, transcript_norm: str, computed: set[str] | None = None) -> list[str]:
    computed = computed or set()
    nums = numbers_in(transcript_norm)
    bad: list[str] = []
    for key in ("qty_t", "max_price_t"):
        v = fields.get(key)
        if v is None or key in computed:
            continue
        s = str(int(v)) if float(v).is_integer() else str(v)
        if s not in nums:
            bad.append(key)
    g = fields.get("grade")
    if g is not None and str(g) not in REFERENCE_NUMBERS:
        bad.append("grade")
    return bad
