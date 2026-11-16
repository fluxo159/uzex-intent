from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import config

Commodity = Literal["cement", "cotton", "lpg", "ai92"]
Grade = Literal["32.5", "42.5"]
PrincipalKind = Literal["ip", "company", "person_2035", "guest"]
PaymentTerms = Literal["after_delivery", "prepay"]

class MandateFields(BaseModel):
    commodity: Commodity | None = None
    grade: Grade | None = None
    qty_t: int | None = None
    region: str | None = None

    @field_validator("region", mode="before")
    @classmethod
    def _empty_region_is_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v
    deadline: dt.date | None = None
    max_price_t: int | None = None
    payment_terms: PaymentTerms = "after_delivery"

class Principal(BaseModel):
    kind: PrincipalKind = "ip"
    display_name: str = "ИП (демо)"
    region: str | None = None
    inn: str | None = None
    principal_id: str | None = None

    def key(self) -> str:
        return self.principal_id or self.inn or self.kind

class LineItem(BaseModel):
    model_config = ConfigDict(strict=False)
    commodity: Commodity
    grade: Grade | None = "32.5"
    qty_t: int = Field(ge=1)

    @field_validator("qty_t", mode="before")
    @classmethod
    def _int_only(cls, v):
        if isinstance(v, bool):
            raise ValueError("количество — целое число тонн")
        if isinstance(v, float) and not v.is_integer():
            raise ValueError("количество — целое число тонн")
        if isinstance(v, str) and not v.strip().isdigit():
            raise ValueError("количество — целое число тонн")
        v = int(v)
        if v < 1:
            raise ValueError("количество должно быть не меньше 1 тонны")
        return v

class AmountRange(BaseModel):
    max_price_t: int = Field(ge=1)
    currency: Literal["UZS"] = "UZS"

class ExecutionWindow(BaseModel):
    not_before: dt.datetime
    not_after: dt.date

class Mandate(BaseModel):
    mandate_id: str
    vct: Literal["uzex.order.open.1"] = "uzex.order.open.1"
    side: Literal["buy", "sell"] = "buy"
    principal: Principal
    line_items: list[LineItem] = Field(min_length=1)
    amount_range: AmountRange
    execution_window: ExecutionWindow
    allowed_regions: list[str] = Field(min_length=1)
    payment_terms: PaymentTerms = "after_delivery"
    expiry: dt.datetime
    natural_language_description: str = ""
    created_at: dt.datetime
    lang: Literal["ru", "uz"] = "ru"

    @property
    def qty_t(self) -> int:
        return self.line_items[0].qty_t

    @property
    def max_price_t(self) -> int:
        return self.amount_range.max_price_t

    @property
    def region(self) -> str:
        return self.allowed_regions[0]

    def signable(self) -> dict:
        d = self.model_dump(mode="python", exclude={"mandate_id"})
        if d["principal"].get("principal_id") is None:
            d["principal"].pop("principal_id", None)
        return d

class FeeBreakdown(BaseModel):
    gross_max: int
    fee_rate: float
    exchange_fee: int
    deposit_rate: float
    deposit_worst: int
    deposit_final: bool = False
    delivery_min_t: int = 0
    delivery_max_t: int = 0
    total_worst: int
    needed_now: int

class Warning_(BaseModel):
    code: str
    params: dict = {}

class MandatePreview(BaseModel):
    fields: MandateFields
    principal: Principal
    fees: FeeBreakdown
    gate: dict
    next_basket: dict
    usual_range: dict
    warnings: list[Warning_] = []
    errors: list[Warning_] = []
    expiry: dt.datetime
    basket_id: str
    mandate_draft: Mandate | None = None
    hash: str | None = None

def compute_expiry(deadline: dt.date, now: dt.datetime) -> dt.datetime:
    end = dt.datetime.combine(deadline, dt.time(23, 59))
    cap = now + dt.timedelta(days=config.MANDATE_MAX_DAYS)
    return min(end, cap)

def check_fields(f: MandateFields, now: dt.datetime) -> tuple[list[Warning_], list[Warning_]]:
    errors: list[Warning_] = []
    warns: list[Warning_] = []
    if f.qty_t is not None and f.qty_t < 1:
        errors.append(Warning_(code="qty_not_positive"))
    if f.max_price_t is not None:
        if f.max_price_t < 1:
            errors.append(Warning_(code="price_not_positive"))
        elif f.commodity in (None, "cement"):
            lo, hi = config.CEMENT_PRICE_SANITY
            if not (lo <= f.max_price_t <= hi):
                warns.append(Warning_(code="price_far_from_market", params={"lo": lo, "hi": hi}))
    if f.deadline is not None and f.deadline < now.date():
        errors.append(Warning_(code="deadline_past"))
    if f.region is not None:
        from .. import regions as _regions
        if f.region not in _regions.REGIONS:
            errors.append(Warning_(code="unknown_region", params={"region": f.region}))
    return errors, warns
