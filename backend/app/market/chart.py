from __future__ import annotations

import datetime as dt
from functools import lru_cache

import duckdb
import pandas as pd

from .. import config
from ..data import loader
from ..regions import normalize_region

GRADE_LABELS = {"32.5": "32,5 (≈М400)", "42.5": "42,5 (≈М500)"}

@lru_cache(maxsize=1)
def hist_df() -> pd.DataFrame:
    try:
        if config.DB_PATH.exists():
            return loader.query("SELECT * FROM deals_hist")
    except Exception:  # noqa: BLE001 — база может строиться параллельно; CSV надёжнее
        pass
    return loader.load_hist()

def normalize_grade_param(grade: str | None) -> str | None:
    if grade is None or str(grade).strip() == "":
        return None
    g = loader.normalize_grade(grade)
    return g

def normalize_region_param(region: str | None) -> str | None:
    if region is None or str(region).strip() == "":
        return None
    from ..regions import REGIONS
    if region in REGIONS:
        return region
    return normalize_region(region) or "__unknown__"

def _filtered(df: pd.DataFrame, grade: str | None, region: str | None,
              date_from: dt.date | None, date_to: dt.date | None) -> pd.DataFrame:
    d = df
    if grade:
        d = d[d["grade"] == grade]
    if region:
        d = d[d["region"] == region]
    if date_from:
        d = d[pd.to_datetime(d["date"]).dt.date >= date_from]
    if date_to:
        d = d[pd.to_datetime(d["date"]).dt.date <= date_to]
    return d

def _counts(d: pd.DataFrame) -> dict:
    return {
        "cancelled_excluded": int(d["cancelled"].sum()),
        "suspect_excluded": int((d["suspect"] & ~d["cancelled"]).sum()),
    }

def _clean(d: pd.DataFrame) -> pd.DataFrame:
    c = d[~d["cancelled"] & ~d["suspect"]]
    return c[(c["tonnes"] > 0) & c["price_t"].notna()]

def _bucket_key(day: dt.date, bucket: str) -> dt.date:
    if bucket == "week":
        return day - dt.timedelta(days=day.weekday())
    return day

def points(df: pd.DataFrame, grade: str | None = None, region: str | None = None,
           date_from: dt.date | None = None, date_to: dt.date | None = None,
           bucket: str = "day") -> dict:
    if bucket not in ("day", "week"):
        raise ValueError("bucket: day | week")
    d = _filtered(df, grade, region, date_from, date_to)
    counts = _counts(d)
    c = _clean(d).copy()
    if c.empty:
        return {"points": [], "n_points": 0, "n_gaps": 0, **counts, "n_deals_total": 0}
    c["day"] = pd.to_datetime(c["date"]).dt.date
    c["bkt"] = [_bucket_key(x, bucket) for x in c["day"]]
    c["amount"] = c["price_t"] * c["tonnes"]
    c = c.sort_values("day", kind="stable").reset_index(drop=True)
    c["ord"] = range(len(c))
    con = duckdb.connect()
    con.register("c", c[["bkt", "tonnes", "price_t", "amount", "ord"]])
    agg = con.execute(
        """SELECT bkt, SUM(amount) / SUM(tonnes) AS vwap, SUM(tonnes) AS volume_t,
                  COUNT(*) AS n_deals, MIN(price_t) AS pmin, MAX(price_t) AS pmax,
                  arg_min(price_t, ord) AS popen, arg_max(price_t, ord) AS pclose
           FROM c GROUP BY bkt ORDER BY bkt"""
    ).df()
    con.close()
    by_key = {pd.Timestamp(r.bkt).date(): r for r in agg.itertuples()}
    start = _bucket_key(date_from, bucket) if date_from else min(by_key)
    end = _bucket_key(date_to, bucket) if date_to else max(by_key)
    step = dt.timedelta(days=7 if bucket == "week" else 1)
    out, gaps, k = [], 0, start
    while k <= end:
        r = by_key.get(k)
        if r is None:
            gaps += 1
            out.append({"date": k.isoformat(), "vwap": None, "volume_t": None, "n_deals": 0,
                        "min": None, "max": None, "open": None, "close": None})
        else:
            out.append({"date": k.isoformat(), "vwap": int(round(r.vwap)), "volume_t": round(float(r.volume_t), 3),
                        "n_deals": int(r.n_deals), "min": int(round(r.pmin)), "max": int(round(r.pmax)),
                        "open": int(round(r.popen)), "close": int(round(r.pclose))})
        k += step
    return {"points": out, "n_points": len(out), "n_gaps": gaps, **counts, "n_deals_total": int(len(c))}

def _percentile(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)

def corridor_from_prices(prices: list[float]) -> dict | None:
    vals = sorted(float(p) for p in prices)
    if not vals:
        return None
    return {"p10": int(round(_percentile(vals, 0.10))), "p50": int(round(_percentile(vals, 0.50))),
            "p90": int(round(_percentile(vals, 0.90))), "n_deals": len(vals)}

def corridor(df: pd.DataFrame, grade: str | None = None, region: str | None = None,
             end: dt.date | None = None, days: int | None = None) -> dict | None:
    days = days or config.CORRIDOR_DAYS
    end = end or dt.date.fromisoformat(config.DATA_CUTOFF)
    d = _clean(_filtered(df, grade, region, end - dt.timedelta(days=days - 1), end))
    res = corridor_from_prices(list(d["price_t"]))
    if res:
        res.update({"from": (end - dt.timedelta(days=days - 1)).isoformat(), "to": end.isoformat(), "days": days})
    return res

def history_7d(df: pd.DataFrame, grade: str | None, end: dt.date | None = None,
               days: int | None = None, region: str | None = None) -> dict | None:
    days = days or config.REFERENCE_DAYS
    end = end or dt.date.fromisoformat(config.DATA_CUTOFF)
    d = _clean(_filtered(df, grade, region, end - dt.timedelta(days=days - 1), end))
    if d.empty:
        return None
    amount = float((d["price_t"] * d["tonnes"]).sum())
    t = float(d["tonnes"].sum())
    return {"vwap": int(round(amount / t)), "min": int(round(d["price_t"].min())),
            "max": int(round(d["price_t"].max())), "n_deals": int(len(d)),
            "from": (end - dt.timedelta(days=days - 1)).isoformat(), "to": end.isoformat()}

HEADLINE_MIN_DEALS = 10
HEADLINE_MIN_T = 1000.0

def headline_from_points(points: list[dict]) -> dict:
    weeks = [p for p in points if p.get("vwap") is not None]
    if not weeks:
        return {"last_vwap": None, "last_from": None, "prev_vwap": None, "prev_from": None,
                "change_pct": None, "basis": None}
    last = weeks[-1]
    prev = None
    for p in reversed(weeks[:-1]):
        if (p.get("n_deals") or 0) >= HEADLINE_MIN_DEALS and (p.get("volume_t") or 0) >= HEADLINE_MIN_T:
            prev = p
            break
    if prev is None:
        return {"last_vwap": last["vwap"], "last_from": last["date"], "prev_vwap": None, "prev_from": None,
                "change_pct": None, "basis": None}
    pct = round((last["vwap"] - prev["vwap"]) / prev["vwap"] * 100, 1)
    d = dt.date.fromisoformat(prev["date"])
    return {"last_vwap": last["vwap"], "last_from": last["date"], "prev_vwap": prev["vwap"],
            "prev_from": prev["date"], "change_pct": pct,
            "basis": f"к неделе {d.day:02d}.{d.month:02d} ({prev['n_deals']} сделок)"}

def headline(df: pd.DataFrame, grade: str | None = None, region: str | None = None) -> dict:
    return headline_from_points(points(df, grade, region, bucket="week")["points"])
