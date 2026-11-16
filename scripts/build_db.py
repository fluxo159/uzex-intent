import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.data.loader import build_db, connection  # noqa: E402

if __name__ == "__main__":
    p = build_db()
    con = connection()
    for t in ("deals_hist", "deals_main", "price_range", "plant_schedule"):
        print(t, con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
    print("ok:", p)
