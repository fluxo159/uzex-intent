from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import ettn_event as ettn
from . import state_machine as sm
from . import store

router = APIRouter(prefix="/escrow", tags=["escrow"])

Event = Literal["payment_confirmed", "ettn_signed", "ettn_rejected", "timeout", "shipped"]

class EventBody(BaseModel):
    type: Event
    at: str | None = None
    reason: str | None = None
    ettn: dict[str, Any] | None = None
    qty_factor: float | None = None

@router.get("/{deal_id}")
def get_escrow(deal_id: str) -> dict:
    try:
        return store.get(deal_id).to_dict()
    except store.NotFound as e:
        raise HTTPException(404, "сделка не найдена") from e

@router.post("/{deal_id}/event")
def post_event(deal_id: str, body: EventBody) -> dict:
    try:
        esc = store.get(deal_id)
    except store.NotFound as e:
        raise HTTPException(404, "сделка не найдена") from e
    payload: dict[str, Any] = {}
    if body.type == "ettn_signed":
        doc = body.ettn
        if doc is None and body.qty_factor is not None:
            doc = ettn.demo_event(esc.deal_id, esc.qty_t or 0, esc.amount or 0, esc.buyer_inn_masked,
                                  body.at, body.qty_factor)
        payload = {"ettn": doc} if doc else {}
    elif body.type == "ettn_rejected":
        payload = {"reason": body.reason}
    try:
        return store.handle(deal_id, body.type, payload, body.at)
    except ettn.EttnMismatch as e:
        raise HTTPException(404, str(e)) from e
    except sm.TransitionError as e:
        raise HTTPException(409, str(e)) from e
    except (ValueError, TypeError) as e:
        msg = str(e)
        if not any("Ѐ" <= ch <= "ӿ" for ch in msg):
            msg = "накладная заполнена неверно: количество, сумма и число подписей должны быть числами"
        raise HTTPException(422, msg) from e
