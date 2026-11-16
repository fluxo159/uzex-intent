import pytest

from app.intake import extract as ex
from app.intake.parser_offline import normalize
from app.intake.service import parse

def dl(text, today):
    n, _ = normalize(text)
    return ex.extract_deadline(ex.fold(n), today)

@pytest.mark.parametrize("text,iso", [
    ("до 15-го", "2026-11-15"),
    ("до 5-го", "2026-12-05"),
    ("до 8-го", "2026-12-08"),
    ("до 9-го", "2026-11-09"),
    ("до пятнадцатого", "2026-11-15"),
    ("до 15 ноября", "2026-11-15"),
    ("15 ноябргача", "2026-11-15"),
    ("15-noyabrgacha", "2026-11-15"),
    ("25-gacha", "2026-11-25"),
    ("до 1 декабря", "2026-12-01"),
    ("15.11.2026", "2026-11-15"),
    ("срочно", "2026-11-10"),
    ("shoshilinch", "2026-11-10"),
    ("на следующей неделе", "2026-11-09"),
    ("kelasi hafta", "2026-11-09"),
    ("завтра", "2026-11-09"),
    ("ertaga", "2026-11-09"),
    ("до конца месяца", "2026-11-30"),
    ("oy oxirigacha", "2026-11-30"),
    ("через 3 дня", "2026-11-11"),
])
def test_deadline(text, iso, today):
    d = dl(text, today)
    assert d.status == "ok" and d.value == iso, (text, d)

def test_past_is_error(today):
    d = dl("до 5 ноября", today)
    assert d.value is None and d.status == "past" and d.hint == "deadline_past"

def test_past_in_parse():
    r = parse("100 тонн цемента в Карши до 5 ноября не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["deadline"] is None
    assert "deadline" in r["missing_fields"] and "deadline_past" in r["hints"]

def test_none_gives_default():
    r = parse("100 тонн цемента в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["deadline"] == "2026-11-15" and "deadline" in r["defaults"]
    assert "deadline" not in r["missing_fields"]

def test_day_not_price(today):
    r = parse("100 тонн цемента в Карши до 15-го не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["deadline"] == "2026-11-15" and r["fields"]["max_price_t"] == 900000
