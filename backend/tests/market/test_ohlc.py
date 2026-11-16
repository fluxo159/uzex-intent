from app.market import chart
from tests.market.test_chart import mk

def test_open_close_are_first_and_last_deal_of_week():
    df = mk([("2026-10-19", 100, 500_000, "32,5", "Toshkent", "Бажарилган"),
             ("2026-10-21", 100, 520_000, "32,5", "Toshkent", "Бажарилган"),
             ("2026-10-23", 100, 510_000, "32,5", "Toshkent", "Бажарилган")])
    p = [x for x in chart.points(df, "32.5", bucket="week")["points"] if x["vwap"]][0]
    assert p["open"] == 500_000 and p["close"] == 510_000
    assert p["min"] == 500_000 and p["max"] == 520_000
    assert p["min"] <= p["open"] <= p["max"] and p["min"] <= p["close"] <= p["max"]

def test_gap_week_has_null_open_close():
    df = mk([("2026-10-19", 100, 500_000, "32,5", "Toshkent", "Бажарилган"),
             ("2026-11-02", 100, 510_000, "32,5", "Toshkent", "Бажарилган")])
    pts = chart.points(df, "32.5", bucket="week")["points"]
    gap = [x for x in pts if x["n_deals"] == 0][0]
    assert gap["open"] is None and gap["close"] is None
