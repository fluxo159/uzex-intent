from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..audit import sources
from . import service

router = APIRouter(prefix="/explain", tags=["explain"])

class ExplainBody(BaseModel):
    result: dict[str, Any]
    basket: dict[str, Any]
    mandate_id: str
    lang: str | None = None
    history: dict[str, Any] | None = None
    tariff_rows: list[dict[str, Any]] | None = None

@router.get("/{mandate_id}")
def get_explain(mandate_id: str, lang: str | None = None) -> dict:
    run = sources.run_for_mandate(mandate_id)
    if run is None:
        raise HTTPException(404, "поручение ещё не участвовало в корзине")
    try:
        return service.explain_run(run, mandate_id, lang)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

@router.post("")
def post_explain(body: ExplainBody) -> dict:
    tariff = None
    if body.tariff_rows:
        tariff = {(r["from"], r["to"]): int(r["t"]) for r in body.tariff_rows}
    run = {"result": body.result, "basket": body.basket, "tariff": tariff}
    try:
        return service.explain_run(run, body.mandate_id, body.lang, history=body.history)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
