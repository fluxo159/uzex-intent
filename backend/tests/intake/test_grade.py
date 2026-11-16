import pytest

from app.intake import extract as ex
from app.intake.parser_offline import normalize
from app.intake.service import parse

def grade(text):
    n, _ = normalize(text)
    return ex.extract_grade(ex.fold(n))

@pytest.mark.parametrize("text", ["цемент М400", "sement m400", "марка 400", "цемент марки 400", "32,5", "32.5Н",
                                  "M-400", "400 markali sement", "ПЦ 400"])
def test_325(text):
    g = grade(text)
    assert g.status == "ok" and g.value == "32.5"

@pytest.mark.parametrize("text", ["М500", "m500", "марка 500", "42,5", "42.5R"])
def test_425(text):
    g = grade(text)
    assert g.status == "ok" and g.value == "42.5"

def test_m300_missing_with_hint():
    g = grade("цемент М300")
    assert g.value is None and g.status == "invalid" and g.hint == "grade_options"
    r = parse("100 тонн цемента М300 в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["grade"] is None
    assert "grade" in r["missing_fields"]
    assert "grade_options" in r["hints"]

def test_no_grade_default():
    r = parse("100 тонн цемента в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["grade"] == "32.5"
    assert "grade" in r["defaults"] and "grade" not in r["missing_fields"]

def test_qty_not_taken_as_grade():
    assert grade("цемента 200 тонн").status == "none"
