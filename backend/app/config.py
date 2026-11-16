from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_DEMO = ROOT / "data" / "demo"
DB_PATH = ROOT / "data" / "uzex.duckdb"
LOG_DIR = ROOT / "logs" / "clearing"

def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env()

BUYER_FEE_RATE = 0.002016
DEPOSIT_RATES = {"default": 0.10, "cement_conch": 0.05}
DEPOSIT_WORST = 0.10
CEMENT_PRICE_SANITY = (200_000, 3_000_000)
MIN_LOT_T_DEFAULT = 50
CEMENT_WINDOWS = [("11:30", "11:50"), ("16:30", "16:50")]
TRADING_WEEKDAYS = (0, 1, 2, 3, 4)
REFERENCE_DAYS = 7
CORRIDOR_DAYS = 90
ETTN_TOLERANCE = 0.005
PAYMENT_DEADLINE_DAYS = 1
DISPUTE_DAYS = 3
OBJECTION_HOURS = 6
DEMO_SEED = int(os.environ.get("DEMO_SEED", "2035"))
ENGINE_VERSION = "clearing-1.0.0"
MANDATE_MAX_DAYS = 14
BAG_KG = 50
LLM_TIMEOUT_S = 8.0

DEMO_NOW = os.environ.get("DEMO_NOW", "2026-11-08T11:30:00")
DATA_CUTOFF = "2026-11-06"

def offline() -> bool:
    return os.environ.get("DEMO_OFFLINE", "0") == "1"

def now():
    import datetime as _dt
    if os.environ.get("DEMO_CLOCK", "fixed") == "live":
        return _dt.datetime.now().replace(microsecond=0)
    return _dt.datetime.fromisoformat(DEMO_NOW)
