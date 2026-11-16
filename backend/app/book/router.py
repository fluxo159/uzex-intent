from fastapi import APIRouter, HTTPException, Query

from .. import config
from . import store

router = APIRouter(prefix="/book", tags=["book"])

@router.get("/basket/open")
def basket_open(commodity: str = "cement", grade: str = "32.5") -> dict:
    return store.basket_summary(store.open_basket_id(commodity, grade))

@router.get("/basket/{basket_id}")
def basket(basket_id: str, mode: str = Query("buyer", pattern="^(buyer|plant|supervisor)$")) -> dict:
    try:
        out = store.basket_summary(basket_id)
    except KeyError as e:
        raise HTTPException(404, "корзина не найдена") from e
    if mode != "buyer":
        bk = store.get_basket(basket_id)
        out["bids"] = [{"mandate_id": b.mandate_id, "qty_t": b.qty_t, "region": b.region} for b in bk.bids]
        out["asks"] = [a.model_dump(mode="json") for a in bk.asks]
    return out

@router.get("/events")
def events(n: int = Query(5, ge=1, le=50)) -> dict:
    return {"now": config.now().isoformat(timespec="seconds"), "events": store.list_events(n)}

@router.get("/tape")
def tape(n: int = Query(5, ge=1, le=50)) -> dict:
    return store.tape(n)

@router.get("/ladder")
def ladder(basket: str = "open", step: int = Query(10_000, ge=1_000, le=1_000_000)) -> dict:
    from . import views
    try:
        return views.ladder(basket, step)
    except KeyError as e:
        raise HTTPException(404, "корзина не найдена") from e
