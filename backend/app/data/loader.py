from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from .. import config
from ..regions import normalize_region

GRADES = ("32.5", "42.5")

_GRADE_RE = re.compile(r"(32|42)\s*[,.]\s*5")
_MARK_RE = re.compile(r"[мm]\s*-?\s*(400|500)", re.IGNORECASE)

def normalize_grade(raw) -> str:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return "other"
    s = str(raw)
    m = _GRADE_RE.search(s)
    if m:
        return "32.5" if m.group(1) == "32" else "42.5"
    m = _MARK_RE.search(s)
    if m:
        return "32.5" if m.group(1) == "400" else "42.5"
    return "other"

def is_cancelled(status) -> bool:
    return isinstance(status, str) and status.strip().startswith("Бекор")

def price_per_t(amount, tonnes) -> float | None:
    try:
        a = float(amount)
        t = float(tonnes)
    except (TypeError, ValueError):
        return None
    if not (t > 0) or math.isnan(a) or math.isnan(t):
        return None
    return a / t

def is_suspect(price_t, commodity: str = "cement") -> bool:
    if price_t is None or (isinstance(price_t, float) and math.isnan(price_t)):
        return True
    lo, hi = config.CEMENT_PRICE_SANITY
    return not (lo <= float(price_t) <= hi)

def load_hist(path: Path | None = None) -> pd.DataFrame:
    path = path or config.DATA_RAW / "uzex_cement_deals_sample.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.date,
        "tonnes": pd.to_numeric(df["tonnes"], errors="coerce"),
        "price_t": pd.to_numeric(df["price_uzs_per_t"], errors="coerce"),
        "grade": [normalize_grade(g if not pd.isna(g) else p) for g, p in zip(df["strength_class"].astype(str), df["product"])],
        "region": [normalize_region(r) for r in df["region"]],
        "status": df["status"],
    })
    bad = out["grade"] == "other"
    out.loc[bad, "grade"] = [normalize_grade(p) for p in df.loc[bad, "product"]]
    out["cancelled"] = [is_cancelled(s) for s in out["status"]]
    out["suspect"] = [is_suspect(p) or not (t > 0) for p, t in zip(out["price_t"], out["tonnes"])]
    return out

def load_main(path: Path | None = None) -> pd.DataFrame:
    path = path or config.DATA_RAW / "cement_deals_main_2-6nov2026_joined.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    tonnes = pd.to_numeric(df["t"], errors="coerce")
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.date,
        "contract": df["contract"].astype(str),
        "seller": df["seller"].astype(str),
        "wh_region": [normalize_region(w) for w in df["wh"].astype(str)],
        "grade": [normalize_grade(c) if normalize_grade(c) != "other" else normalize_grade(m)
                  for c, m in zip(df["cls"], df["mark"])],
        "pack": df["pack"].astype(str),
        "tonnes": tonnes,
        "price_t": [price_per_t(a, t) for a, t in zip(df["amount"], tonnes)],
        "base_t": pd.to_numeric(df["base_t"], errors="coerce"),
        "lot_t": pd.to_numeric(df["lot"], errors="coerce"),
    })
    out["suspect"] = [is_suspect(p) for p in out["price_t"]]
    return out

def load_price_range(path: Path | None = None) -> pd.DataFrame:
    path = path or config.DATA_RAW / "cement_price_range_oct-nov2026.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame({
        "contract": df["contract"].astype(str),
        "seller": df["seller"].astype(str),
        "grade": [normalize_grade(m) for m in df["mark"]],
        "date": pd.to_datetime(df["date"].astype(str).str.replace(".", "-", regex=False)).dt.date,
        "pmin": pd.to_numeric(df["pmin"], errors="coerce"),
        "pmax": pd.to_numeric(df["pmax"], errors="coerce"),
    })

def _num_ru(s: str) -> float:
    return float(str(s).replace(" ", "").replace(",", "."))

def load_schedule(path: Path | None = None) -> pd.DataFrame:
    path = path or config.DATA_RAW / "cem_sched.json"
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for month, items in raw.items():
        for it in items:
            rows.append({"month": month.replace("_", "-"), "plant_raw": it[0], "volume_t": _num_ru(it[1])})
    return pd.DataFrame(rows)

def build_db(db_path: Path | None = None) -> Path:
    db_path = Path(db_path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    for name, df in {
        "deals_hist": load_hist(),
        "deals_main": load_main(),
        "price_range": load_price_range(),
        "plant_schedule": load_schedule(),
    }.items():
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    con.close()
    return db_path

@lru_cache(maxsize=1)
def connection() -> duckdb.DuckDBPyConnection:
    if not config.DB_PATH.exists():
        build_db()
    return duckdb.connect(str(config.DB_PATH), read_only=True)

def query(sql: str, params: list | None = None) -> pd.DataFrame:
    return connection().execute(sql, params or []).df()
