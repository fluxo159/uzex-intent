from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..i18n.uzlatin import to_latin

CREATED = "CREATED"
DEPOSIT_HELD = "DEPOSIT_HELD"
MATCHED = "MATCHED"
PAID_IN_FULL = "PAID_IN_FULL"
DELIVERED = "DELIVERED"
RELEASED = "RELEASED"
DISPUTED = "DISPUTED"
CANCELLED = "CANCELLED"
TIMEOUT_RELEASED = "TIMEOUT_RELEASED"

STATES = (CREATED, DEPOSIT_HELD, MATCHED, PAID_IN_FULL, DELIVERED, RELEASED, DISPUTED, CANCELLED, TIMEOUT_RELEASED)
FINAL = {RELEASED, CANCELLED, TIMEOUT_RELEASED}

TRANSITIONS: dict[tuple[str, str], str] = {
    (CREATED, "mandate_signed"): DEPOSIT_HELD,
    (DEPOSIT_HELD, "cleared"): MATCHED,
    (MATCHED, "payment_confirmed"): PAID_IN_FULL,
    (MATCHED, "timeout"): CANCELLED,
    (PAID_IN_FULL, "ettn_signed"): DELIVERED,
    (PAID_IN_FULL, "ettn_rejected"): DISPUTED,
    (DELIVERED, "auto_release"): RELEASED,
    (DISPUTED, "timeout"): TIMEOUT_RELEASED,
}
INFO_EVENTS = {(PAID_IN_FULL, "shipped")}

LABELS_RU = {
    CREATED: "поручение создано", DEPOSIT_HELD: "задаток заблокирован на вашем счёте",
    MATCHED: "сделка в корзине, ждём оплату остатка", PAID_IN_FULL: "оплачено полностью, деньги у биржи",
    DELIVERED: "получатель подписал накладную", RELEASED: "деньги переведены заводу",
    DISPUTED: "спор: деньги заморожены", CANCELLED: "отменено: остаток не оплачен вовремя",
    TIMEOUT_RELEASED: "спор не подтверждён в срок, деньги переведены заводу",
}
LABELS_UZ = {
    CREATED: "топшириқ яратилди", DEPOSIT_HELD: "закалат ҳисобингизда блокланди",
    MATCHED: "битим саватда, қолган тўловни кутамиз", PAID_IN_FULL: "тўлиқ тўланди, пул биржада",
    DELIVERED: "қабул қилувчи юк хатини имзолади", RELEASED: "пул заводга ўтказилди",
    DISPUTED: "низо: пул музлатилди", CANCELLED: "бекор қилинди: қолган тўлов ўз вақтида қилинмади",
    TIMEOUT_RELEASED: "низо муддатида тасдиқланмади, пул заводга ўтказилди",
}

class TransitionError(Exception):
    pass

def parse_time(t: Any = None) -> dt.datetime:
    if t is None:
        t = config.DEMO_NOW
    if isinstance(t, dt.datetime):
        return t.replace(tzinfo=None)
    return dt.datetime.fromisoformat(str(t).replace("Z", "")).replace(tzinfo=None)

def add_business_days(t: dt.datetime, n: int) -> dt.datetime:
    d = t
    left = n
    while left > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d

def add_business_hours(t: dt.datetime, hours: int, start: int = 9, end: int = 18) -> dt.datetime:
    cur = t
    left = dt.timedelta(hours=hours)
    while left > dt.timedelta(0):
        if cur.weekday() >= 5 or cur.hour >= end:
            cur = dt.datetime.combine(cur.date() + dt.timedelta(days=1), dt.time(start))
            continue
        if cur.hour < start:
            cur = dt.datetime.combine(cur.date(), dt.time(start))
        day_end = dt.datetime.combine(cur.date(), dt.time(end))
        step = min(left, day_end - cur)
        cur += step
        left -= step
    return cur

@dataclass
class Escrow:
    deal_id: str
    mandate_id: str | None = None
    state: str = CREATED
    qty_t: int | None = None
    amount: int | None = None
    deposit: int | None = None
    seller: str | None = None
    buyer_inn_masked: str | None = None
    deadline: str | None = None
    deadline_kind: str | None = None
    dispute_reason: str | None = None
    grey_path: str | None = None
    history: list[dict] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "deal_id": self.deal_id, "mandate_id": self.mandate_id, "state": self.state,
            "label_ru": LABELS_RU[self.state], "label_uz": to_latin(LABELS_UZ[self.state]), "final": self.state in FINAL,
            "qty_t": self.qty_t, "amount": self.amount, "deposit": self.deposit, "seller": self.seller,
            "buyer_inn_masked": self.buyer_inn_masked,
            "deadline": self.deadline, "deadline_kind": self.deadline_kind,
            "dispute_reason": self.dispute_reason, "grey_path": self.grey_path,
            "allowed_events": allowed_events(self.state),
            "history": list(self.history), "log": list(self.log),
            "demo": True, "demo_note_ru": "ДЕМО: в проде — РКП и exdoc",
        }

def allowed_events(state: str) -> list[str]:
    ev = [e for (s, e) in TRANSITIONS if s == state and e != "auto_release"]
    ev += [e for (s, e) in INFO_EVENTS if s == state]
    return sorted(ev)

def _move(esc: Escrow, event: str, to: str, at: dt.datetime, note: str | None = None) -> None:
    esc.history.append({"from": esc.state, "event": event, "to": to, "at": at.isoformat(timespec="minutes"),
                        **({"note": note} if note else {})})
    esc.state = to

def _set_timer(esc: Escrow, at: dt.datetime) -> None:
    esc.deadline = esc.deadline_kind = None
    if esc.state == MATCHED:
        esc.deadline = add_business_days(at, config.PAYMENT_DEADLINE_DAYS).isoformat(timespec="minutes")
        esc.deadline_kind = "payment"
    elif esc.state == DISPUTED:
        esc.deadline = add_business_days(at, config.DISPUTE_DAYS).isoformat(timespec="minutes")
        esc.deadline_kind = "dispute"
    elif esc.state == RELEASED:
        esc.deadline = add_business_days(at, 1).isoformat(timespec="minutes")
        esc.deadline_kind = "payout_to_seller"

def apply(esc: Escrow, event: str, at: Any = None, **data: Any) -> Escrow:
    t = parse_time(at)
    if esc.state in FINAL:
        raise TransitionError(f"из {esc.state} переходов нет: деньги уже распределены")
    if (esc.state, event) in INFO_EVENTS:
        if event == "shipped":
            until = add_business_hours(t, config.OBJECTION_HOURS)
            esc.grey_path = (f"сегодня: без документа {config.OBJECTION_HOURS} рабочих часов на возражение "
                             f"(до {until.isoformat(timespec='minutes')}), потом деньги уходят продавцу молча")
            esc.log.append({"event": event, "at": t.isoformat(timespec="minutes"), "info": True})
        return esc
    to = TRANSITIONS.get((esc.state, event))
    if to is None:
        raise TransitionError(f"событие {event} недопустимо в состоянии {esc.state}")
    if event == "cleared":
        for k in ("qty_t", "amount", "seller", "buyer_inn_masked"):
            if data.get(k) is not None:
                setattr(esc, k, data[k])
    if event == "mandate_signed" and data.get("deposit") is not None:
        esc.deposit = int(data["deposit"])
    note = None
    if event == "timeout" and esc.state == MATCHED:
        note = "задаток покупателя → продавцу (как сегодня)"
    if event == "ettn_rejected":
        esc.dispute_reason = data.get("reason") or "получатель отказал в подписи"
        note = f"черновик претензии, {config.DISPUTE_DAYS} раб. дня"
    _move(esc, event, to, t, note)
    if to == DELIVERED:
        _move(esc, "auto_release", RELEASED, t, "выплата продавцу ≤ 1 раб. дня")
    _set_timer(esc, t)
    return esc

def dispute(esc: Escrow, reason: str, at: Any = None) -> Escrow:
    return apply(esc, "ettn_rejected", at, reason=reason)
