from fastapi import APIRouter, HTTPException

from . import demand as dm

router = APIRouter(prefix="/plant", tags=["plant"])

@router.get("/{seller}/demand")
def plant_demand(seller: str) -> dict:
    try:
        return dm.demand(seller)
    except KeyError as e:
        raise HTTPException(404, "завод не найден в книге") from e

@router.get("")
def plants() -> dict:
    from ..book import store
    return {"plants": store.plants_list()}
