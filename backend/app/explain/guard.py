from __future__ import annotations

import os
import re
from collections import Counter
from typing import Callable

from .. import config

_NUM = re.compile(r"\d[\d   ]*(?:[.,]\d+)?")

def numbers(text: str) -> Counter:
    out: Counter = Counter()
    for m in _NUM.finditer(text):
        s = re.sub(r"[   ]", "", m.group(0)).replace(",", ".").rstrip(".")
        out[s] += 1
    return out

def enabled() -> bool:
    return os.environ.get("EXPLAIN_LLM", "0") == "1" and not config.offline()

def guarded_rephrase(sentences: list[str], lang: str,
                     rephrase: Callable[[list[str], str], list[str]] | None,
                     force: bool = False) -> tuple[list[str], str]:
    if rephrase is None or not (force or enabled()):
        return list(sentences), "template"
    try:
        out = rephrase(list(sentences), lang)
    except Exception:  # noqa: BLE001 — таймаут/сеть/что угодно: числа важнее красоты
        return list(sentences), "template"
    if not isinstance(out, list) or len(out) != len(sentences) or not all(isinstance(x, str) for x in out):
        return list(sentences), "template"
    for a, b in zip(sentences, out):
        if numbers(a) != numbers(b):
            return list(sentences), "template"
    return out, "llm"
