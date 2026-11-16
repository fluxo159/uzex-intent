from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

_EPOCH = dt.datetime(2026, 1, 1)

def _int_qty(v):
    if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
        raise ValueError("qty_t must be an integer number of tonnes")
    if isinstance(v, str):
        raise ValueError("qty_t must be an integer")
    return int(v)

class Bid(BaseModel):
    mandate_id: str
    qty_t: int = Field(ge=1)
    max_price_t: int = Field(ge=0)
    region: str
    created_at: dt.datetime = _EPOCH

    _q = field_validator("qty_t", mode="before")(classmethod(lambda cls, v: _int_qty(v)))

class Ask(BaseModel):
    offer_id: str
    seller: str
    qty_t: int = Field(ge=1)
    min_price_t: int = Field(ge=0)
    warehouse_region: str
    min_lot_t: int = Field(default=1, ge=0)
    created_at: dt.datetime = _EPOCH
    deposit_rate: float = 0.10

    _q = field_validator("qty_t", mode="before")(classmethod(lambda cls, v: _int_qty(v)))

class Basket(BaseModel):
    basket_id: str
    commodity: str = "cement"
    grade: str = "32.5"
    close_time: dt.datetime = _EPOCH
    bids: list[Bid] = []
    asks: list[Ask] = []

class Allocation(BaseModel):
    mandate_id: str
    offer_id: str
    seller: str
    qty_t: int
    price_t: int
    tariff_t: int
    delivered_price_t: int
    lot_group_id: str

UnfilledReason = Literal["price_below_clearing", "no_supply", "lot_not_formed"]
AskUnfilledReason = Literal["price_above_clearing", "no_demand", "lot_not_formed"]
TieBreak = Literal["max_volume", "min_surplus", "market_pressure", "reference", "midpoint", "none"]

class Unfilled(BaseModel):
    mandate_id: str
    qty_t: int
    reason: UnfilledReason
    fill_at_max_price_t: Optional[int] = None

class AskUnfilled(BaseModel):
    offer_id: str
    qty_t: int
    reason: AskUnfilledReason

class Aggregates(BaseModel):
    demand_curve: list[tuple[int, int]]
    supply_curve: list[tuple[int, int]]
    total_demand: int
    total_supply: int
    n_bids: int
    n_asks: int
    n_executed_bids: int
    n_executed_asks: int
    marginal_side: Literal["demand", "supply", "balanced", "none"]
    best_bid: Optional[int] = None
    best_ask: Optional[int] = None

class LotGroup(BaseModel):
    lot_group_id: str
    offer_id: str
    seller: str
    qty_t: int
    n_mandates: int
    min_lot_t: int
    regions: dict[str, int]

class ClearingResult(BaseModel):
    run_id: str
    basket_id: str
    engine_version: str
    clearing_price_t: Optional[int]
    executed_qty_t: int
    allocations: list[Allocation]
    unfilled: list[Unfilled]
    asks_unfilled: list[AskUnfilled]
    aggregates: Aggregates
    tie_break_used: TieBreak
    lot_groups: list[LotGroup] = []
    reference_price_t: Optional[int] = None
    inputs_hash: str
