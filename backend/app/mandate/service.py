from __future__ import annotations

import datetime as dt

from .. import config
from ..book import store
from ..clearing.delivery import demo_tariff, tariff_t
from ..signing import demo_signer
from . import canonical, fees
from .schema import (AmountRange, ExecutionWindow, FeeBreakdown, LineItem, Mandate, MandateFields,
                     MandatePreview, Principal, Warning_, check_fields, compute_expiry)

REQUIRED = ("commodity", "qty_t", "region", "max_price_t")

def default_deadline(now: dt.datetime) -> dt.date:
    bi = store.open_basket(after=now)
    return (bi.window_start + dt.timedelta(days=7)).date()

def delivery_range(region: str | None, commodity: str = "cement", grade: str = "32.5") -> tuple[int, int]:
    if not region:
        return (0, 0)
    tar = demo_tariff()
    vals = [t for oid, a in store.S.asks.items()
            if store.S.ask_meta[oid]["commodity"] == commodity and store.S.ask_meta[oid]["grade"] == grade
            and (t := tariff_t(tar, a.warehouse_region, region)) is not None]
    return (min(vals), max(vals)) if vals else (0, 0)

def usual_range(grade: str | None) -> dict:
    try:
        from ..market import chart
        c = chart.corridor(chart.hist_df(), grade or "32.5", None)
    except Exception:
        c = None
    if not c:
        return {"lo": None, "hi": None, "days": config.CORRIDOR_DAYS, "available": False}
    return {"lo": c["p10"], "hi": c["p90"], "p10": c["p10"], "p90": c["p90"], "mid": c.get("p50"), "days": c.get("days", config.CORRIDOR_DAYS),
            "n_deals": c.get("n_deals"), "available": True, "source": "данные UZEX, двойной аукцион",
            "data_cutoff": config.DATA_CUTOFF}

def mandate_id_from_hash(h: str) -> str:
    return f"{h[:4].upper()}-{h[4:6].upper()}"

def build_mandate(f: MandateFields, principal: Principal, transcript: str, lang: str, now: dt.datetime) -> Mandate:
    deadline = f.deadline or default_deadline(now)
    m = Mandate(
        mandate_id="pending", principal=principal,
        line_items=[LineItem(commodity=f.commodity or "cement", grade=f.grade or "32.5", qty_t=f.qty_t)],
        amount_range=AmountRange(max_price_t=f.max_price_t),
        execution_window=ExecutionWindow(not_before=now, not_after=deadline),
        allowed_regions=[f.region], payment_terms=f.payment_terms,
        expiry=compute_expiry(deadline, now), natural_language_description=transcript or "",
        created_at=now, lang=lang if lang in ("ru", "uz") else "ru",
    )
    h = canonical.sha256(m.signable())
    return m.model_copy(update={"mandate_id": mandate_id_from_hash(h)})

def run_gate(principal: Principal, f: MandateFields, funds_available: int | None) -> dict:
    try:
        from ..gate import eligibility
        return eligibility.check(
            principal.model_dump(),
            [{"commodity": f.commodity or "cement", "qty_t": f.qty_t, "max_price_t": f.max_price_t,
              "allowed_regions": [f.region] if f.region else []}],
            funds_available=funds_available)
    except Exception as e:
        return {"status": "warning", "checks": [{"name": "gate", "level": "warning", "passed": False,
                                                 "reason": f"проверка недоступна: {type(e).__name__}"}],
                "demo": True}

def preview(f: MandateFields, principal: Principal, transcript: str = "", lang: str = "ru",
            funds_available: int | None = None, now: dt.datetime | None = None) -> MandatePreview:
    now = now or config.now()
    errors, warns = check_fields(f, now)
    missing = [k for k in REQUIRED if getattr(f, k) is None]
    for k in missing:
        errors.append(Warning_(code="missing", params={"field": k}))
    if f.grade is None and f.commodity in (None, "cement"):
        warns.append(Warning_(code="grade_default", params={"grade": "32.5"}))
    if f.deadline is None:
        warns.append(Warning_(code="deadline_default"))
    if principal.region is None:
        principal = principal.model_copy(update={"region": f.region})
    bi = store.open_basket(f.commodity or "cement", f.grade or "32.5", after=now)
    if f.deadline is not None and f.deadline < bi.window_start.date():
        warns.append(Warning_(code="deadline_before_next_basket",
                              params={"next": bi.window_start.isoformat(timespec="minutes")}))
    dr = delivery_range(f.region, f.commodity or "cement", f.grade or "32.5")
    ok_numbers = f.qty_t is not None and f.qty_t >= 1 and f.max_price_t is not None and f.max_price_t >= 1
    fb = FeeBreakdown(**fees.compute(f.qty_t, f.max_price_t, dr)) if ok_numbers else FeeBreakdown(
        gross_max=0, fee_rate=config.BUYER_FEE_RATE, exchange_fee=0, deposit_rate=config.DEPOSIT_WORST,
        deposit_worst=0, delivery_min_t=dr[0], delivery_max_t=dr[1], total_worst=0, needed_now=0)
    gate = run_gate(principal, f, funds_available) if ok_numbers else {"status": "pending", "checks": []}
    if gate.get("status") == "blocked":
        errors.append(Warning_(code="gate_blocked"))
    draft = h = None
    deadline = f.deadline or default_deadline(now)
    if not errors:
        draft = build_mandate(f, principal, transcript, lang, now)
        h = canonical.sha256(draft.signable())
    return MandatePreview(
        fields=f, principal=principal, fees=fb, gate=gate, next_basket=store.basket_public(bi),
        usual_range=usual_range(f.grade), warnings=warns, errors=errors,
        expiry=compute_expiry(deadline, now), basket_id=bi.basket_id, mandate_draft=draft, hash=h)

class SignError(ValueError):
    pass

def sign(m: Mandate, funds_available: int | None = None) -> dict:
    f = MandateFields(commodity=m.line_items[0].commodity, grade=m.line_items[0].grade, qty_t=m.qty_t,
                      region=m.region, deadline=m.execution_window.not_after, max_price_t=m.max_price_t,
                      payment_terms=m.payment_terms)
    errors, _ = check_fields(f, m.created_at)
    if errors:
        raise SignError(errors[0].code)
    gate = run_gate(m.principal, f, funds_available)
    if gate.get("status") == "blocked":
        raise SignError("gate_blocked")
    h = canonical.sha256(m.signable())
    m = m.model_copy(update={"mandate_id": mandate_id_from_hash(h)})
    signed_at = max(config.now(), m.created_at)
    with store.LOCK:
        def _still_open(k: str) -> bool:
            b = store.mandate_basket(k)
            return b is not None and store.S.baskets[b].status == "open"
        existing = next((k for k, v in store.S.hashes.items() if v == h and _still_open(k)), None)
        if existing is not None:
            return {"mandate_id": existing, "hash": h, "receipt": store.S.receipts[existing], "demo": True,
                    "basket_id": store.mandate_basket(existing), "gate": gate, "duplicate": True,
                    "signed_at": store.S.receipts[existing].get("signed_at")}
        receipt = demo_signer.sign(h, signed_at)
        mid = store.add_mandate(m, h, receipt)
    try:
        from ..audit import sources
        sources.register_mandate(mid, hash=h, receipt=receipt, inn=m.principal.inn, kind=m.principal.kind,
                                 region=m.region)
    except Exception:
        pass
    return {"mandate_id": mid, "hash": h, "receipt": receipt, "demo": True, "basket_id": store.mandate_basket(mid),
            "gate": gate, "signed_at": signed_at.isoformat(timespec="seconds")}
