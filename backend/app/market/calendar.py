from __future__ import annotations

import calendar as _cal
import datetime as dt
import re
from functools import lru_cache

import pandas as pd

from .. import config
from ..data import loader
from ..i18n.uzlatin import to_latin

TRADING_WEEKDAYS = getattr(config, "TRADING_WEEKDAYS", (0, 1, 2, 3, 4))
N_WINDOWS = 5
NOTE_RU = "ориентир; время окон — подтвердить"
NOTE_UZ = "тахминий; савдо вақти — тасдиқлансин"

_LEGAL = {"mchj", "xk", "qk", "ooo", "ip", "ao", "aj", "sp", "mchj", "chj", "llc", "jsc",
          "маъсулияти", "чекланган", "жамияти", "ооо", "ип", "ао", "сп", "мчж"}

def parse_now(now: str | dt.datetime | None = None) -> dt.datetime:
    if now is None:
        now = config.DEMO_NOW
    if isinstance(now, dt.datetime):
        return now.replace(tzinfo=None)
    return dt.datetime.fromisoformat(str(now)).replace(tzinfo=None)

def _hm(s: str) -> dt.time:
    h, m = s.split(":")
    return dt.time(int(h), int(m))

def next_windows(now: str | dt.datetime | None = None, n: int = N_WINDOWS,
                 weekdays: tuple[int, ...] = TRADING_WEEKDAYS,
                 windows: list[tuple[str, str]] | None = None) -> list[dict]:
    now_dt = parse_now(now)
    wins = sorted((_hm(a), _hm(b)) for a, b in (windows or config.CEMENT_WINDOWS))
    if not wins or not weekdays:
        return []
    out: list[dict] = []
    day = now_dt.date()
    for _ in range(366):
        if day.weekday() in weekdays:
            for a, b in wins:
                start, end = dt.datetime.combine(day, a), dt.datetime.combine(day, b)
                if end <= now_dt:
                    continue
                out.append({
                    "date": day.isoformat(), "weekday": day.weekday(),
                    "start": start.isoformat(timespec="minutes"), "end": end.isoformat(timespec="minutes"),
                    "label": f"{day.strftime('%d.%m')} {a.strftime('%H:%M')}–{b.strftime('%H:%M')}",
                    "is_open_now": start <= now_dt < end,
                    "to_confirm": True,
                })
                if len(out) >= n:
                    return out
        day += dt.timedelta(days=1)
    return out

def working_days(year: int, month: int, weekdays: tuple[int, ...] = TRADING_WEEKDAYS) -> int:
    ndays = _cal.monthrange(year, month)[1]
    return sum(1 for d in range(1, ndays + 1) if dt.date(year, month, d).weekday() in weekdays)

def _tokens(name: str) -> set[str]:
    s = str(name).lower().replace("’", "").replace("‘", "").replace("'", "")
    toks = {t for t in re.split(r"[^0-9a-zа-яёўқғҳ]+", s) if t}
    return toks - _LEGAL

def match_plant(plant_raw: str, sellers: list[str]) -> str | None:
    pt = _tokens(plant_raw)
    best = None
    for s in sellers:
        st = _tokens(s)
        if st and st <= pt and (best is None or len(st) > len(_tokens(best))):
            best = s
    return best

def last_base_prices(main: pd.DataFrame) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = main[main["base_t"].notna() & (main["seller"] != "?")]
    for seller, g in d.groupby("seller"):
        for sub in (g[(g["grade"] == "32.5") & (g["pack"] == "навал")], g[g["grade"] == "32.5"], g):
            if not sub.empty:
                r = sub.sort_values("date").iloc[-1]
                out[seller] = {"base_price_t": int(r["base_t"]), "base_price_date": str(r["date"]),
                               "grade": r["grade"], "pack": r["pack"]}
                break
    return out

def plants_for_month(schedule: pd.DataFrame, main: pd.DataFrame, month: str,
                     weekdays: tuple[int, ...] = TRADING_WEEKDAYS) -> list[dict]:
    y, m = (int(x) for x in month.split("-"))
    wd = working_days(y, m, weekdays)
    sellers = sorted(set(main["seller"]) - {"?"})
    bases = last_base_prices(main)
    rows = []
    for r in schedule[schedule["month"] == month].itertuples():
        seller = match_plant(r.plant_raw, sellers)
        base = bases.get(seller) if seller else None
        rows.append({
            "plant": seller or r.plant_raw, "plant_raw": r.plant_raw, "month": month,
            "month_volume_t": round(float(r.volume_t), 2), "working_days": wd,
            "daily_volume_t": int(round(float(r.volume_t) / wd)) if wd else None,
            "base_price_t": base["base_price_t"] if base else None,
            "base_price_date": base["base_price_date"] if base else None,
        })
    rows.sort(key=lambda x: -x["month_volume_t"])
    return rows

@lru_cache(maxsize=1)
def _sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    return loader.load_schedule(), loader.load_main()

def build(now: str | dt.datetime | None = None, n: int = N_WINDOWS) -> dict:
    wins = next_windows(now, n)
    schedule, main = _sources()
    months = sorted({w["date"][:7] for w in wins})
    available = set(schedule["month"])
    plants = []
    for mth in months:
        src = mth if mth in available else (max(available) if available else None)
        if src:
            for p in plants_for_month(schedule, main, src):
                p["for_month"] = mth
                p["schedule_month_used"] = src
                plants.append(p)
    return {"now": parse_now(now).isoformat(timespec="minutes"), "windows": wins, "plants": plants,
            "note_ru": NOTE_RU, "note_uz": to_latin(NOTE_UZ), "source": "графики заводов UZEX (cem_sched.json)"}
