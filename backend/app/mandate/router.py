from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..auth import deps, settings
from ..auth.context import Ctx
from ..middleware import ratelimit
from . import service
from .schema import AmountRange, ExecutionWindow, LineItem, Mandate, MandateFields, MandatePreview, Principal

router = APIRouter(prefix="/mandate", tags=["mandate"])

_STRICT = ConfigDict(extra="forbid")
QTY_RANGE = (1, 10_000)
PRICE_RANGE = (10_000, 100_000_000)

def _in_range(v, lo: int, hi: int, what: str):
    if settings.enforce() and v is not None and not isinstance(v, bool) and isinstance(v, (int, float)) and not (lo <= v <= hi):
        raise ValueError(f"{what}: от {lo:,} до {hi:,}".replace(",", " "))
    return v

class FieldsIn(MandateFields):
    model_config = _STRICT
    region: str | None = Field(None, max_length=64)

    @field_validator("qty_t")
    @classmethod
    def _qty(cls, v):
        return _in_range(v, *QTY_RANGE, "количество, т")

    @field_validator("max_price_t")
    @classmethod
    def _price(cls, v):
        return _in_range(v, *PRICE_RANGE, "потолок цены, сум/т")

class PrincipalIn(Principal):
    model_config = _STRICT
    display_name: str = Field("ИП (демо)", max_length=120)
    region: str | None = Field(None, max_length=64)
    inn: str | None = Field(None, max_length=14)
    principal_id: str | None = Field(None, max_length=40)

class LineItemIn(LineItem):
    model_config = ConfigDict(strict=False, extra="forbid")

    @field_validator("qty_t")
    @classmethod
    def _qty_range(cls, v):
        return _in_range(v, *QTY_RANGE, "количество, т")

class AmountRangeIn(AmountRange):
    model_config = _STRICT

    @field_validator("max_price_t")
    @classmethod
    def _price(cls, v):
        return _in_range(v, *PRICE_RANGE, "потолок цены, сум/т")

class WindowIn(ExecutionWindow):
    model_config = _STRICT

class MandateIn(Mandate):
    model_config = _STRICT
    mandate_id: str = Field(max_length=64)
    principal: PrincipalIn
    line_items: list[LineItemIn] = Field(min_length=1, max_length=1)
    amount_range: AmountRangeIn
    execution_window: WindowIn
    allowed_regions: list[str] = Field(min_length=1, max_length=3)
    natural_language_description: str = Field("", max_length=2000)

class PreviewBody(BaseModel):
    model_config = _STRICT
    fields: FieldsIn
    principal: PrincipalIn = PrincipalIn()
    transcript_norm: str = Field("", max_length=2000)
    lang: str = Field("ru", max_length=8)
    funds_available: int | None = Field(None, ge=0, le=10**13)

class SignBody(BaseModel):
    model_config = _STRICT
    mandate: MandateIn
    funds_available: int | None = Field(None, ge=0, le=10**13)

def _bind(principal: Principal, c: Ctx) -> None:
    if settings.enforce():
        principal.principal_id = c.principal_id

def _sign_limits(c: Ctx) -> None:
    if not settings.enforce() or c.level == "admin":
        return
    lim = settings.limits()
    if c.level == "guest":
        plan = [("sign_guest_hour", c.participant_key, "sign_limit"), ("sign_ip_hour", c.ip, "sign_ip_limit")]
    else:
        plan = [("sign_jury_hour", c.participant_key, "sign_limit")]
    for bucket, key, code in plan:
        ok, retry = ratelimit.check(bucket, key, *lim[bucket])
        if not ok:
            raise deps.too_many(code, retry, n=lim[bucket][0], scope=bucket)
    for bucket, key, _ in plan:
        ratelimit.hit(bucket, key, *lim[bucket])

@router.post("/preview", response_model=MandatePreview)
def mandate_preview(body: PreviewBody, c: Ctx = Depends(deps.ctx)) -> MandatePreview:
    _bind(body.principal, c)
    return service.preview(body.fields, body.principal, body.transcript_norm, body.lang, body.funds_available)

@router.post("/sign")
def mandate_sign(body: SignBody, c: Ctx = Depends(deps.ctx)) -> dict:
    _sign_limits(c)
    _bind(body.mandate.principal, c)
    try:
        return service.sign(body.mandate, body.funds_available)
    except service.SignError as e:
        raise HTTPException(422, {"code": str(e)}) from e

@router.get("/mine")
def mandate_mine(principal_id: str | None = None, c: Ctx = Depends(deps.ctx)) -> dict:
    from ..book import views
    if not settings.enforce():
        if not principal_id:
            raise HTTPException(422, "нужен principal_id")
        return {"principal_id": principal_id, "mandates": views.mine(principal_id)}
    if c.level == "admin" and principal_id:
        return {"principal_id": principal_id, "mandates": views.mine(principal_id)}
    if principal_id and principal_id != c.principal_id:
        return {"principal_id": principal_id, "mandates": []}
    return {"principal_id": c.principal_id, "mandates": views.mine(c.principal_id)}

@router.get("/{mandate_id}")
def mandate_get(mandate_id: str, c: Ctx = Depends(deps.ctx)) -> dict:
    from ..book import store
    m = store.S.mandates.get(mandate_id)
    if m is None or (settings.enforce() and c.level != "admin" and m.principal.principal_id != c.principal_id):
        raise HTTPException(404, "поручение не найдено")
    return {"mandate": m.model_dump(mode="json"), "hash": store.S.hashes[mandate_id],
            "receipt": store.S.receipts[mandate_id], "status": store.S.status[mandate_id],
            "remaining_t": store.S.remaining[mandate_id], "basket_id": store.mandate_basket(mandate_id)}
