from __future__ import annotations

import datetime as dt
import hashlib
import json
from decimal import Decimal
from typing import Any

def _norm(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _norm(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_norm(v) for v in o]
    if isinstance(o, dt.datetime):
        if o.tzinfo is not None:
            o = o.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return o.replace(microsecond=0).isoformat() + "Z"
    if isinstance(o, dt.date):
        return o.isoformat()
    if isinstance(o, float):
        if o.is_integer():
            return int(o)
        return format(Decimal(repr(o)), "f")
    if isinstance(o, Decimal):
        return format(o, "f")
    if hasattr(o, "model_dump"):
        return _norm(o.model_dump(mode="python"))
    return o

def dumps(obj: Any) -> str:
    return json.dumps(_norm(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256(obj: Any) -> str:
    return hashlib.sha256(dumps(obj).encode("utf-8")).hexdigest()
