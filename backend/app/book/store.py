from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass, field

from .. import config
from ..clearing.models import Ask, Basket, Bid, ClearingResult
from ..mandate.schema import Mandate

@dataclass
class BasketInfo:
    basket_id: str
    commodity: str
    grade: str
    window_start: dt.datetime
    window_end: dt.datetime
    status: str = "open"
    mandate_ids: list[str] = field(default_factory=list)
    run_id: str | None = None

@dataclass
class State:
    mandates: dict[str, Mandate] = field(default_factory=dict)
    receipts: dict[str, dict] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    status: dict[str, str] = field(default_factory=dict)
    remaining: dict[str, int] = field(default_factory=dict)
    asks: dict[str, Ask] = field(default_factory=dict)
    ask_meta: dict[str, dict] = field(default_factory=dict)
    plants: dict[str, Ask] = field(default_factory=dict)
    baskets: dict[str, BasketInfo] = field(default_factory=dict)
    open_by_key: dict[tuple[str, str], str] = field(default_factory=dict)
    runs: dict[str, ClearingResult] = field(default_factory=dict)
    run_baskets: dict[str, Basket] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    closed_at: dict[str, str] = field(default_factory=dict)

S = State()
LOCK = threading.RLock()

def reset() -> None:
    global S
    S = State()
LOCK = threading.RLock()

def _windows_after(t: dt.datetime, n: int = 1) -> list[tuple[dt.datetime, dt.datetime]]:
    out = []
    day = t.date()
    wins = sorted((dt.time.fromisoformat(a), dt.time.fromisoformat(b)) for a, b in config.CEMENT_WINDOWS)
    weekdays = getattr(config, "TRADING_WEEKDAYS", (0, 1, 2, 3, 4))
    for _ in range(400):
        if day.weekday() in weekdays:
            for a, b in wins:
                s, e = dt.datetime.combine(day, a), dt.datetime.combine(day, b)
                if e > t:
                    out.append((s, e))
                    if len(out) == n:
                        return out
        day += dt.timedelta(days=1)
    return out

def basket_id_for(commodity: str, grade: str, start: dt.datetime) -> str:
    return f"B-{commodity}-{grade}-{start:%Y%m%d-%H%M}"

def open_basket(commodity: str = "cement", grade: str = "32.5", after: dt.datetime | None = None) -> BasketInfo:
    key = (commodity, grade)
    bid_ = S.open_by_key.get(key)
    if bid_ and S.baskets[bid_].status == "open":
        return S.baskets[bid_]
    start, end = _windows_after(after or config.now())[0]
    bi = BasketInfo(basket_id_for(commodity, grade, start), commodity, grade, start, end)
    if bi.basket_id in S.baskets:
        start, end = _windows_after(end)[0]
        bi = BasketInfo(basket_id_for(commodity, grade, start), commodity, grade, start, end)
    S.baskets[bi.basket_id] = bi
    S.open_by_key[key] = bi.basket_id
    return bi

def open_basket_id(commodity: str = "cement", grade: str = "32.5") -> str:
    return open_basket(commodity, grade).basket_id

def basket_public(bi: BasketInfo) -> dict:
    return {"basket_id": bi.basket_id, "commodity": bi.commodity, "grade": bi.grade,
            "window_start": bi.window_start.isoformat(timespec="minutes"),
            "window_end": bi.window_end.isoformat(timespec="minutes"), "status": bi.status,
            "window": f"{bi.window_start:%H:%M}–{bi.window_end:%H:%M}", "date": bi.window_start.date().isoformat(),
            "close_time": bi.window_end.isoformat(timespec="minutes"),
            "run_id": bi.run_id, "to_confirm": True}

def _event(kind: str, at: dt.datetime, qty_t: int, region: str | None = None, seller: str | None = None,
           status: str | None = None, basket_id: str | None = None, price_t: int | None = None) -> None:
    S.events.append({"kind": kind, "at": at.isoformat(timespec="seconds"), "qty_t": int(qty_t), "region": region,
                     "seller": seller, "status": status, "basket_id": basket_id, "price_t": price_t,
                     "seq": len(S.events)})

def add_mandate(m: Mandate, doc_hash: str, receipt: dict) -> str:
    mid = m.mandate_id
    k = 2
    while mid in S.mandates:
        mid = f"{m.mandate_id}-{k}"
        k += 1
    if mid != m.mandate_id:
        m = m.model_copy(update={"mandate_id": mid})
    li = m.line_items[0]
    bi = open_basket(li.commodity, li.grade or "32.5", after=m.created_at)
    S.mandates[mid] = m
    S.hashes[mid] = doc_hash
    S.receipts[mid] = receipt
    S.status[mid] = "open"
    S.remaining[mid] = li.qty_t
    bi.mandate_ids.append(mid)
    _event("mandate", m.created_at, li.qty_t, region=m.region, basket_id=bi.basket_id)
    return mid

def add_ask(ask: Ask, commodity: str = "cement", grade: str = "32.5", meta: dict | None = None) -> str:
    S.asks[ask.offer_id] = ask
    S.plants[ask.offer_id] = ask
    S.ask_meta[ask.offer_id] = {"commodity": commodity, "grade": grade, **(meta or {})}
    _event("ask", ask.created_at, ask.qty_t, region=ask.warehouse_region, seller=ask.seller)
    return ask.offer_id

def mandate_basket(mandate_id: str) -> str | None:
    last = None
    for bi in S.baskets.values():
        if mandate_id in bi.mandate_ids:
            last = bi.basket_id
    return last

def get_basket(basket_id: str) -> Basket:
    bi = S.baskets.get(basket_id)
    if bi is None:
        raise KeyError(basket_id)
    bids = []
    for mid in bi.mandate_ids:
        m = S.mandates[mid]
        if S.status.get(mid) not in ("open", "partial"):
            continue
        if m.expiry < bi.window_end:
            continue
        bids.append(Bid(mandate_id=mid, qty_t=S.remaining[mid], max_price_t=m.max_price_t, region=m.region,
                        created_at=m.created_at))
    asks = [a for oid, a in S.asks.items()
            if S.ask_meta[oid]["commodity"] == bi.commodity and S.ask_meta[oid]["grade"] == bi.grade]
    return Basket(basket_id=bi.basket_id, commodity=bi.commodity, grade=bi.grade, close_time=bi.window_end,
                  bids=bids, asks=asks)

def basket_summary(basket_id: str) -> dict:
    bk = get_basket(basket_id)
    bi = S.baskets[basket_id]
    return {**basket_public(bi), "n_buyers": len(bk.bids), "demand_t": sum(b.qty_t for b in bk.bids),
            "n_plants": len(bk.asks), "supply_t": sum(a.qty_t for a in bk.asks)}

def record_run(basket_id: str, basket: Basket, result: ClearingResult) -> None:
    bi = S.baskets[basket_id]
    bi.status = "closed"
    bi.run_id = result.run_id
    S.runs[result.run_id] = result
    S.run_baskets[result.run_id] = basket
    got: dict[str, int] = {}
    for a in result.allocations:
        got[a.mandate_id] = got.get(a.mandate_id, 0) + a.qty_t
    at = max(config.now(), max((m.created_at for m in S.mandates.values()), default=config.now()))
    S.closed_at[basket_id] = at.isoformat(timespec="seconds")
    nxt = None
    for b in basket.bids:
        q = got.get(b.mandate_id, 0)
        left = S.remaining[b.mandate_id] - q
        S.remaining[b.mandate_id] = left
        if q > 0:
            _event("filled", at, q, region=b.region, status="filled", basket_id=basket_id)
        if left <= 0:
            S.status[b.mandate_id] = "filled"
            continue
        S.status[b.mandate_id] = "partial" if q > 0 else "open"
        if nxt is None:
            S.open_by_key.pop((bi.commodity, bi.grade), None)
            nxt = open_basket(bi.commodity, bi.grade, after=bi.window_end)
        nxt.mandate_ids.append(b.mandate_id)
        _event("waiting", at, left, region=b.region, status="waiting", basket_id=nxt.basket_id)
    sold: dict[str, int] = {}
    for a in result.allocations:
        sold[a.offer_id] = sold.get(a.offer_id, 0) + a.qty_t
    for oid, q in sold.items():
        ask = S.asks[oid]
        left = ask.qty_t - q
        if left > 0:
            S.asks[oid] = ask.model_copy(update={"qty_t": left})
        else:
            S.asks.pop(oid)
    if nxt is None:
        S.open_by_key.pop((bi.commodity, bi.grade), None)
        open_basket(bi.commodity, bi.grade, after=bi.window_end)
    _event("basket_closed", at, result.executed_qty_t, status="closed", basket_id=basket_id,
           price_t=result.clearing_price_t)

def list_events(n: int = 5) -> list[dict]:
    ev = sorted(S.events, key=lambda e: (e["at"], e["seq"]), reverse=True)
    return ev[:n]

def tape(n: int = 5) -> dict:
    items = []
    for e in list_events(n):
        if e["kind"] == "basket_closed":
            items.append({"kind": "basket_closed", "who": None, "qty_t": e["qty_t"], "at": e["at"],
                          "status": "closed", "price_t": e["price_t"], "basket_id": e["basket_id"]})
            continue
        kind = "offer" if e["kind"] == "ask" else "mandate"
        items.append({"kind": kind, "who": e["seller"] if kind == "offer" else e["region"], "qty_t": e["qty_t"],
                      "at": e["at"], "status": e["status"]})
    return {"now": config.now().isoformat(timespec="seconds"), "items": items}

def plants_list() -> list[dict]:
    out = []
    for oid, a in S.plants.items():
        cur = S.asks.get(oid)
        out.append({"offer_id": oid, "seller": a.seller, "warehouse_region": a.warehouse_region,
                    "price_t": a.min_price_t, "qty_t": cur.qty_t if cur else 0, "offered_t": a.qty_t,
                    "min_lot_t": a.min_lot_t, "sold_out": cur is None})
    return out
