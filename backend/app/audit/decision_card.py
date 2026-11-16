from __future__ import annotations

from typing import Any

from ..mandate import canonical
from ..market.objects import g, items, to_plain
from ..i18n.uzlatin import to_latin

APPROVED_BY = "принципал (подпись поручения)"
APPEAL_CHANNEL = {
    "ru": "обжалование: служба надзора биржи, ответ в 10 рабочих дней; сделка и все входы восстанавливаются по хешам",
    "uz": "шикоят: биржа назорат хизмати, жавоб 10 иш кунида; битим ва барча кириш маълумотлари хеш орқали тикланади",
}
DECIDED_BY = "детерминированный движок единой цены (без нейросети)"

def explanation_hash(explanation: dict | None) -> str | None:
    if not explanation:
        return None
    core = {k: explanation.get(k) for k in ("mandate_id", "run_id", "outcome", "sentences_ru", "sentences_uz")}
    return canonical.sha256(core)

def build(result: Any, mandate_id: str, mandate_hash: str | None = None, signer_receipt: Any = None,
          explanation: dict | None = None, escrow_state: str | None = None) -> dict:
    run_id = str(g(result, "run_id"))
    mine = [to_plain(a) for a in items(result, "allocations") if str(g(a, "mandate_id")) == str(mandate_id)]
    unf = [to_plain(u) for u in items(result, "unfilled") if str(g(u, "mandate_id")) == str(mandate_id)]
    card = {
        "deal_id": f"{run_id}:{mandate_id}", "run_id": run_id, "basket_id": g(result, "basket_id"),
        "mandate_id": str(mandate_id),
        "mandate_hash": mandate_hash, "inputs_hash": g(result, "inputs_hash"),
        "engine_version": g(result, "engine_version"), "tie_break_used": g(result, "tie_break_used"),
        "clearing_price": g(result, "clearing_price_t"), "reference_price": g(result, "reference_price_t"),
        "allocations": mine, "unfilled": unf,
        "explanation_hash": explanation_hash(explanation),
        "signer_receipt": to_plain(signer_receipt),
        "approved_by": APPROVED_BY, "decided_by": DECIDED_BY,
        "appeal_channel": APPEAL_CHANNEL["ru"], "appeal_channel_uz": to_latin(APPEAL_CHANNEL["uz"]),
        "escrow_state": escrow_state,
        "demo_note": "ДЕМО-подпись: в проде — E-IMZO, ID-карта",
    }
    card["card_hash"] = canonical.sha256(card)
    card["hashes_present"] = all(card[k] for k in ("inputs_hash", "card_hash")) and \
        (mandate_hash is None or bool(card["mandate_hash"]))
    return card

def verify(card: dict) -> bool:
    body = {k: v for k, v in card.items() if k not in ("card_hash", "hashes_present")}
    return canonical.sha256(body) == card.get("card_hash")
