from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from . import eligibility, registry

router = APIRouter(prefix="/gate", tags=["gate"])

class Principal(BaseModel):
    kind: str = Field(description="ip | company | person_2035 | guest")
    inn: str | None = None
    region: str | None = None

class LineItem(BaseModel):
    commodity: str = "cement"
    qty_t: int = Field(ge=1)
    max_price_t: int = Field(ge=1)
    allowed_regions: list[str] = []

class GateBody(BaseModel):
    principal: Principal
    line_items: list[LineItem]
    funds_available: int | None = None
    registry_down: bool = False

@router.post("/check")
def gate_check(body: GateBody) -> dict:
    return eligibility.check(body.principal.model_dump(), [i.model_dump() for i in body.line_items],
                             body.funds_available, body.registry_down)

@router.get("/registry")
def gate_registry() -> dict[str, Any]:
    return {"demo": True, "label": registry.DEMO_LABEL,
            "entities": [{k: e[k] for k in ("inn", "kind", "name", "region", "status")} for e in registry.entities()]}
