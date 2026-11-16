import datetime as dt

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.market import calendar as cal

def test_from_monday_10_first_is_1130():
    w = cal.next_windows("2026-11-09T10:00:00")
    assert len(w) == 5
    assert w[0]["start"] == "2026-11-09T11:30" and w[0]["end"] == "2026-11-09T11:50"
    assert [x["start"] for x in w] == ["2026-11-09T11:30", "2026-11-09T16:30", "2026-11-10T11:30",
                                       "2026-11-10T16:30", "2026-11-11T11:30"]
    assert all(x["to_confirm"] for x in w)

def test_from_monday_12_first_is_1630():
    assert cal.next_windows("2026-11-09T12:00:00")[0]["start"] == "2026-11-09T16:30"

def test_open_window_is_first_and_marked():
    w = cal.next_windows("2026-11-09T11:40:00")
    assert w[0]["start"] == "2026-11-09T11:30" and w[0]["is_open_now"] is True
    assert w[1]["is_open_now"] is False

def test_window_end_boundary_excluded():
    assert cal.next_windows("2026-11-09T11:50:00")[0]["start"] == "2026-11-09T16:30"

def test_sunday_demo_now_skips_to_monday():
    w = cal.next_windows("2026-11-08T10:00:00")
    assert w[0]["start"] == "2026-11-09T11:30"

def test_friday_evening_skips_weekend():
    w = cal.next_windows("2026-11-13T17:00:00")
    assert w[0]["start"] == "2026-11-16T11:30"

def test_weekdays_by_constant():
    w = cal.next_windows("2026-11-08T10:00:00", weekdays=(6,))
    assert w[0]["start"] == "2026-11-08T11:30"
    assert cal.next_windows("2026-11-08T10:00:00", weekdays=()) == []

def test_working_days():
    assert cal.working_days(2026, 11) == 21

def test_match_plant_names():
    sellers = ["Toshkent Conch Cement", "Qarshi Conch Cement", "Huaxin Cement Jizzakh",
               "Shangfeng-Bridge of Friendship", "Jizzakh Cement Plant"]
    assert cal.match_plant("TOSHKENT CONCH CEMENT MCHJ QK", sellers) == "Toshkent Conch Cement"
    assert cal.match_plant("ООО QARSHI CONCH CEMENT", sellers) == "Qarshi Conch Cement"
    assert cal.match_plant("ООО ИП HUAXIN CEMENT JIZZAKH", sellers) == "Huaxin Cement Jizzakh"
    assert cal.match_plant("SHANGFENG-BRIDGE OF FRIENDSHIP МАЪСУЛИЯТИ ЧЕКЛАНГАН ЖАМИЯТИ", sellers) \
        == "Shangfeng-Bridge of Friendship"
    assert cal.match_plant("JIZZAKH CEMENT PLANT MCHJ", sellers) == "Jizzakh Cement Plant"
    assert cal.match_plant("АО Бекабадцемент", sellers) is None

def test_daily_volume_and_base_price():
    sched = pd.DataFrame([{"month": "2026-11", "plant_raw": "TOSHKENT CONCH CEMENT MCHJ QK", "volume_t": 210000.0}])
    main = pd.DataFrame([
        {"date": dt.date(2026, 11, 5), "seller": "Toshkent Conch Cement", "grade": "32.5", "pack": "навал", "base_t": 500000.0},
        {"date": dt.date(2026, 11, 6), "seller": "Toshkent Conch Cement", "grade": "32.5", "pack": "навал", "base_t": 490000.0},
        {"date": dt.date(2026, 11, 6), "seller": "Toshkent Conch Cement", "grade": "32.5", "pack": "мешки", "base_t": 530000.0},
    ])
    p = cal.plants_for_month(sched, main, "2026-11")[0]
    assert p["daily_volume_t"] == 10000 and p["working_days"] == 21
    assert p["base_price_t"] == 490000 and p["base_price_date"] == "2026-11-06"

def test_endpoint_calendar_real_data():
    j = TestClient(app).get("/market/calendar", params={"now": "2026-11-09T10:00:00"}).json()
    assert len(j["windows"]) == 5 and j["windows"][0]["start"] == "2026-11-09T11:30"
    tc = [p for p in j["plants"] if p["plant"] == "Toshkent Conch Cement"]
    assert tc and tc[0]["base_price_t"] == 490000 and tc[0]["daily_volume_t"] == 10000
    assert "подтвердить" in j["note_ru"]
    assert TestClient(app).get("/market/calendar", params={"now": "вчера"}).status_code == 422
