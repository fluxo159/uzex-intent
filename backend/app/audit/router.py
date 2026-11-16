from fastapi import APIRouter, HTTPException

from ..market.objects import g, items
from . import decision_card, sources

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/{deal_id}")
def get_audit(deal_id: str) -> dict:
    try:
        run_id, mandate_id = sources.split_deal_id(deal_id)
    except KeyError as e:
        raise HTTPException(404, "сделка не найдена") from e
    run = sources.get_run(run_id)
    if run is None or not any(str(g(b, "mandate_id")) == mandate_id for b in items(run["basket"], "bids")):
        raise HTTPException(404, "сделка не найдена")
    info = sources.mandate_info(mandate_id)
    explanation = None
    try:
        from ..explain import service
        explanation = service.explain_run(run, mandate_id, "ru")
    except Exception:  # noqa: BLE001 — паспорт без объяснения лучше, чем ошибка
        explanation = None
    escrow_state = None
    try:
        from ..escrow import store
        escrow_state = store.get(sources.deal_id(run_id, mandate_id)).state
    except Exception:  # noqa: BLE001
        escrow_state = None
    return decision_card.build(run["result"], mandate_id, info.get("hash"), info.get("receipt"),
                               explanation, escrow_state)
