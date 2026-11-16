from app.market.chart import headline_from_points

def wk(date, vwap, n, t):
    return {"date": date, "vwap": vwap, "volume_t": t, "n_deals": n, "min": vwap, "max": vwap}

def test_outlier_week_is_skipped():
    pts = [wk("2026-10-12", 535_585, 117, 38_098), wk("2026-10-19", 569_210, 121, 48_651),
           wk("2026-10-26", 766_000, 5, 500), wk("2026-11-02", 507_317, 163, 76_057)]
    h = headline_from_points(pts)
    assert h["prev_from"] == "2026-10-19"
    assert h["change_pct"] == round((507_317 - 569_210) / 569_210 * 100, 1)
    assert "19.10" in h["basis"] and "121" in h["basis"]

def test_gaps_and_nulls_ignored():
    pts = [wk("2026-10-19", 569_210, 121, 48_651), {"date": "2026-10-26", "vwap": None, "volume_t": None, "n_deals": 0},
           wk("2026-11-02", 507_317, 163, 76_057)]
    assert headline_from_points(pts)["prev_from"] == "2026-10-19"

def test_no_reference_gives_null():
    pts = [wk("2026-10-26", 766_000, 5, 500), wk("2026-11-02", 507_317, 163, 76_057)]
    h = headline_from_points(pts)
    assert h["change_pct"] is None and h["last_vwap"] == 507_317

def test_empty():
    assert headline_from_points([])["change_pct"] is None
