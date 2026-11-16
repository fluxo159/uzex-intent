from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import require_level
from . import scenario

router = APIRouter(prefix="/demo", tags=["demo"])

@router.post("/reset", dependencies=[Depends(require_level("admin"))])
def demo_reset() -> dict:
    return scenario.reset(1)

@router.post("/step/{n}", dependencies=[Depends(require_level("admin"))])
def demo_step(n: int) -> dict:
    if n not in (0, 1, 2):
        raise HTTPException(422, "шаги 0, 1, 2")
    return scenario.reset(n)

@router.get("/scenario")
def demo_scenario() -> dict:
    s = scenario.scenario()
    return {"note": s["note"], "buyers": [{"key": b["key"], "region": b["region"], "lang": b["lang"],
                                           "phrase": b["phrase"], "kind": b["kind"]} for b in s["buyers"]]}
