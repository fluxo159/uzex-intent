from __future__ import annotations

from typing import Any

def g(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def items(obj: Any, key: str) -> list:
    v = g(obj, key, None)
    return list(v) if v else []

def to_plain(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return to_plain(obj.model_dump())
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses
        return to_plain(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    return obj
