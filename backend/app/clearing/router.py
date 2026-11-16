from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import require_level
from . import service

router = APIRouter(prefix="/clearing", tags=["clearing"])

@router.post("/run/{basket_id}", dependencies=[Depends(require_level("admin"))])
def clearing_run(basket_id: str) -> dict:
    from ..book import store
    if basket_id == "open":
        basket_id = store.open_basket_id()
    try:
        r = service.close_basket(basket_id)
    except KeyError as e:
        raise HTTPException(404, "корзина не найдена") from e
    return {**r.model_dump(mode="json"), "next_basket_id": store.open_basket_id()}

@router.get("/history")
def clearing_history(commodity: str = "cement", grade: str = "32.5") -> dict:
    from ..book import views
    return {"commodity": commodity, "grade": grade, "baskets": views.history(commodity, grade)}

@router.get("/result/{run_id}")
def clearing_result(run_id: str) -> dict:
    try:
        return service.get_result(run_id).model_dump(mode="json")
    except KeyError as e:
        raise HTTPException(404, "прогон не найден") from e
