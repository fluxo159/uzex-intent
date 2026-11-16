from __future__ import annotations

from typing import Any, Callable

from ..market.objects import g, items

_RUNS: dict[str, dict] = {}
_BY_MANDATE: dict[str, str] = {}
_MANDATES: dict[str, dict] = {}
_resolver: Callable[[str], dict | None] | None = None

def reset() -> None:
    _RUNS.clear()
    _BY_MANDATE.clear()
    _MANDATES.clear()

def register_run(result: Any, basket: Any, tariff: Any = None, **extra: Any) -> str:
    run_id = str(g(result, "run_id"))
    _RUNS[run_id] = {"result": result, "basket": basket, "tariff": tariff, "extra": extra}
    for b in items(basket, "bids"):
        _BY_MANDATE[str(g(b, "mandate_id"))] = run_id
    return run_id

def register_mandate(mandate_id: str, **info: Any) -> None:
    _MANDATES.setdefault(str(mandate_id), {}).update(info)

def set_resolver(fn: Callable[[str], dict | None] | None) -> None:
    global _resolver
    _resolver = fn

def get_run(run_id: str) -> dict | None:
    r = _RUNS.get(str(run_id))
    if r is None and _resolver is not None:
        r = _resolver(str(run_id))
    return r

def run_for_mandate(mandate_id: str) -> dict | None:
    rid = _BY_MANDATE.get(str(mandate_id))
    return get_run(rid) if rid else None

def mandate_info(mandate_id: str) -> dict:
    return dict(_MANDATES.get(str(mandate_id), {}))

def deal_id(run_id: str, mandate_id: str) -> str:
    return f"{run_id}:{mandate_id}"

def split_deal_id(did: str) -> tuple[str, str]:
    if ":" not in did:
        rid = _BY_MANDATE.get(did)
        if rid is None:
            raise KeyError(did)
        return rid, did
    a, b = did.split(":", 1)
    return a, b

def runs() -> list[str]:
    return list(_RUNS)
