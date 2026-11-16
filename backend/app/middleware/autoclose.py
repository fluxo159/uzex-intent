from __future__ import annotations

import asyncio
import datetime as dt
import logging

from ..auth import settings

log = logging.getLogger("intent.autoclose")
_state: dict = {"next_at": None, "last": None}

def next_slot(now: dt.datetime, every_min: int) -> dt.datetime:
    base = now.replace(second=0, microsecond=0)
    minutes = base.hour * 60 + base.minute
    nxt = (minutes // every_min + 1) * every_min
    return base.replace(hour=0, minute=0) + dt.timedelta(minutes=nxt)

def close_open_baskets() -> list[dict]:
    from ..book import store
    from ..clearing import service
    from . import cache
    done = []
    seen = {mid for b in store.S.baskets.values() if b.status == "closed" for mid in b.mandate_ids}
    for bi in list(store.S.baskets.values()):
        if bi.status != "open":
            continue
        try:
            bk = store.get_basket(bi.basket_id)
        except KeyError:
            continue
        if not any(b.mandate_id not in seen for b in bk.bids):
            continue
        r = service.close_basket(bi.basket_id)
        done.append({"basket_id": bi.basket_id, "run_id": r.run_id, "clearing_price_t": r.clearing_price_t})
    if done:
        cache.clear()
    return done

def info() -> dict | None:
    every = settings.autoclose_min()
    if not every:
        return None
    nxt = _state["next_at"] or next_slot(dt.datetime.now(), every)
    return {"every_min": every, "next_at": nxt.isoformat(timespec="minutes"), "last": _state["last"]}

async def loop() -> None:
    while True:
        every = settings.autoclose_min()
        if not every:
            return
        nxt = next_slot(dt.datetime.now(), every)
        _state["next_at"] = nxt
        await asyncio.sleep(max(1.0, (nxt - dt.datetime.now()).total_seconds()))
        try:
            done = await asyncio.to_thread(close_open_baskets)
            _state["last"] = {"at": dt.datetime.now().isoformat(timespec="seconds"), "closed": done}
            if done:
                log.info("autoclose %s", done)
        except Exception:
            log.exception("autoclose failed")

def start() -> asyncio.Task | None:
    if not settings.autoclose_min():
        return None
    return asyncio.create_task(loop(), name="autoclose")
