import datetime as dt

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.data import loader
from app.main import app
from app.market import chart

D = dt.date

def mk(rows):
    df = pd.DataFrame(rows, columns=["date", "tonnes", "price_t", "grade_raw", "region_raw", "status"])
    from app.regions import normalize_region
    return pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.date, "tonnes": df["tonnes"].astype(float),
        "price_t": df["price_t"].astype(float),
        "grade": [loader.normalize_grade(g) for g in df["grade_raw"]],
        "region": [normalize_region(r) for r in df["region_raw"]],
        "status": df["status"],
        "cancelled": [loader.is_cancelled(s) for s in df["status"]],
        "suspect": [loader.is_suspect(p) or not (t > 0) for p, t in zip(df["price_t"], df["tonnes"])],
    })

OK = "Бажарилган"
CANC = "Бекор қилинган (Тўланмаган)"

def test_vwap_three_deals_by_hand():
    df = mk([("2026-11-02", 100, 500_000, "32,5Н", "Samarqand viloyati", OK),
             ("2026-11-02", 50, 530_000, "ЦЕМ II А-И 32,5", "Самарканд", OK),
             ("2026-11-02", 50, 560_000, "32.5 Н", "Samarkand", OK)])
    p = chart.points(df, "32.5")["points"]
    assert len(p) == 1
    assert p[0] == {"date": "2026-11-02", "vwap": 522_500, "volume_t": 200.0, "n_deals": 3,
                    "min": 500_000, "max": 560_000, "open": 500_000, "close": 560_000}

def test_grade_with_comma_does_not_break():
    df = mk([("2026-11-02", 10, 500_000, "32,5Н", "Jizzax viloyati", OK),
             ("2026-11-02", 10, 700_000, "42,5", "Jizzax viloyati", OK)])
    assert chart.points(df, "32.5")["points"][0]["vwap"] == 500_000
    assert chart.points(df, "42.5")["points"][0]["vwap"] == 700_000
    assert chart.normalize_grade_param("32,5") == "32.5"
    assert chart.normalize_grade_param("М500") == "42.5"

def test_day_without_deals_is_null_I17():
    df = mk([("2026-11-02", 10, 500_000, "32.5", "Samarkand", OK),
             ("2026-11-05", 10, 520_000, "32.5", "Samarkand", OK)])
    res = chart.points(df, "32.5")
    days = {x["date"]: x for x in res["points"]}
    assert len(res["points"]) == 4 and res["n_gaps"] == 2
    for d in ("2026-11-03", "2026-11-04"):
        assert days[d]["vwap"] is None and days[d]["volume_t"] is None and days[d]["n_deals"] == 0
        assert days[d]["min"] is None and days[d]["max"] is None

def test_cancelled_excluded_and_counted():
    df = mk([("2026-11-02", 10, 500_000, "32.5", "Samarkand", OK),
             ("2026-11-02", 1000, 900_000, "32.5", "Samarkand", CANC)])
    res = chart.points(df, "32.5")
    assert res["points"][0]["vwap"] == 500_000 and res["points"][0]["n_deals"] == 1
    assert res["cancelled_excluded"] == 1

def test_suspect_excluded_and_counted():
    df = mk([("2026-11-02", 10, 500_000, "32.5", "Samarkand", OK),
             ("2026-11-02", 10, 5_000_000_000, "32.5", "Samarkand", OK),
             ("2026-11-02", 10, 500, "32.5", "Samarkand", OK),
             ("2026-11-02", 0, 500_000, "32.5", "Samarkand", OK)])
    res = chart.points(df, "32.5")
    assert res["points"][0]["vwap"] == 500_000 and res["points"][0]["n_deals"] == 1
    assert res["suspect_excluded"] == 3

def test_region_three_spellings_same_filter():
    df = mk([("2026-11-02", 10, 500_000, "32.5", "Farg‘ona viloyati", OK),
             ("2026-11-02", 10, 520_000, "32.5", "Ферганская область", OK),
             ("2026-11-02", 10, 540_000, "32.5", "Фарғона вилояти", OK),
             ("2026-11-02", 10, 900_000, "32.5", "Samarkand", OK)])
    for spelling in ("Fergana", "Farg'ona", "Фергана", "Фарғона"):
        r = chart.normalize_region_param(spelling)
        assert chart.points(df, "32.5", r)["points"][0]["vwap"] == 520_000

def test_filter_without_data_empty():
    df = mk([("2026-11-02", 10, 500_000, "32.5", "Samarkand", OK)])
    assert chart.points(df, "32.5", "Namangan")["points"] == []
    assert chart.points(df, "32.5", chart.normalize_region_param("Луна"))["points"] == []
    assert chart.points(df, "42.5")["points"] == []

def test_one_day_one_deal():
    df = mk([("2026-11-02", 7, 510_000, "32.5", "Samarkand", OK)])
    p = chart.points(df)["points"]
    assert p == [{"date": "2026-11-02", "vwap": 510_000, "volume_t": 7.0, "n_deals": 1,
                  "min": 510_000, "max": 510_000, "open": 510_000, "close": 510_000}]

def test_weekly_bucket():
    df = mk([("2026-11-02", 10, 500_000, "32.5", "Samarkand", OK),
             ("2026-11-06", 10, 600_000, "32.5", "Samarkand", OK),
             ("2026-11-17", 10, 700_000, "32.5", "Samarkand", OK)])
    p = chart.points(df, bucket="week")["points"]
    assert [x["date"] for x in p] == ["2026-11-02", "2026-11-09", "2026-11-16"]
    assert p[0]["vwap"] == 550_000 and p[1]["vwap"] is None and p[2]["vwap"] == 700_000

def test_corridor_known_array():
    c = chart.corridor_from_prices(list(range(100, 1100, 100)))
    assert c == {"p10": 190, "p50": 550, "p90": 910, "n_deals": 10}
    assert chart.corridor_from_prices([]) is None

def test_real_data_months_without_deals_are_gaps():
    df = loader.load_hist()
    res = chart.points(df)
    by = {}
    for x in res["points"]:
        by.setdefault(x["date"][:7], []).append(x)
    for empty_month in ("2025-06", "2025-09", "2026-05", "2026-09"):
        assert all(x["vwap"] is None for x in by[empty_month]), empty_month
    assert sum(1 for x in by["2026-08"] if x["vwap"] is not None) == 1
    assert res["cancelled_excluded"] == 119
    assert res["points"][-1]["date"] == "2026-11-06"

def test_history_7d():
    df = mk([("2026-10-30", 10, 400_000, "32.5", "Samarkand", OK),
             ("2026-11-02", 10, 500_000, "32.5", "Samarkand", OK),
             ("2026-11-06", 30, 600_000, "32.5", "Samarkand", OK)])
    h = chart.history_7d(df, "32.5", D(2026, 11, 6))
    assert h["vwap"] == 575_000 and h["min"] == 500_000 and h["max"] == 600_000 and h["n_deals"] == 2
    assert chart.history_7d(df, "42.5", D(2026, 11, 6)) is None

def test_endpoint_chart():
    r = TestClient(app).get("/market/chart", params={"grade": "32.5"})
    assert r.status_code == 200
    j = r.json()
    assert j["n_points"] > 100 and j["n_gaps"] > 0 and j["corridor"]["p10"] <= j["corridor"]["p90"]
    assert any(x["vwap"] is None for x in j["points"])
    r = TestClient(app).get("/market/chart", params={"region": "Луна"})
    assert r.status_code == 200 and r.json()["points"] == [] and r.json()["region_unknown"] is True
    assert TestClient(app).get("/market/chart", params={"commodity": "cotton"}).status_code == 404
