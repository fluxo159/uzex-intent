import time

import pytest

from app.intake.service import numbers_confirmed, parse

ALL_REQUIRED = {"commodity", "qty_t", "region", "max_price_t"}

@pytest.mark.parametrize("text", ["", "   ", "🔥🔥👍", "😀 🚚 🏗️", "12345", "1 000 000", None])
def test_empty_emoji_digits_missing_all(text):
    r = parse(text, allow_llm=False)
    assert ALL_REQUIRED <= set(r["missing_fields"])
    assert r["fields"]["qty_t"] is None and r["fields"]["max_price_t"] is None

def test_five_thousand_chars():
    text = ("200 тонн цемента М400 в Наманган " + "бла " * 2000)[:5000]
    t0 = time.perf_counter()
    r = parse(text, allow_llm=False)
    assert time.perf_counter() - t0 < 0.3
    assert r["fields"]["qty_t"] == 200 and r["fields"]["region"] == "Namangan"

def test_longer_than_limit_is_truncated():
    r = parse("цемент " * 3000, allow_llm=False)
    assert len(r["transcript_norm"]) <= 5000

def test_correction_20_200_missing_qty():
    r = parse("20 тонн… нет, 200 тонн цемента в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["qty_t"] is None
    assert "qty_t" in r["missing_fields"] and "qty_conflict" in r["hints"]

def test_no_numbers():
    r = parse("нужен цемент в Карши", allow_llm=False)
    assert r["missing_fields"] == ["qty_t", "max_price_t"]

def test_two_regions_destination():
    r = parse("из Ташкента в Карши 100 тонн цемента не дороже 900000", allow_llm=False)
    assert r["fields"]["region"] == "Qashqadaryo"

def test_two_regions_ambiguous():
    r = parse("Ташкент Карши 100 тонн цемента 900000", allow_llm=False)
    assert r["fields"]["region"] is None and "region" in r["missing_fields"]

def test_m300():
    r = parse("100 тонн цемента М300 в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["grade"] is None and "grade" in r["missing_fields"] and "grade_options" in r["hints"]

def test_bags_qty_and_price():
    r = parse("400 мешков цемента в Карши по 45 тысяч за мешок", allow_llm=False)
    assert r["fields"]["qty_t"] == 20 and r["fields"]["max_price_t"] == 900000
    assert set(r["computed"]) == {"qty_t", "max_price_t"}
    assert "price_per_bag" in r["hints"] and "qty_from_bags" in r["hints"]
    assert numbers_confirmed(r)

def test_two_bags_not_integer():
    r = parse("2 мешка цемента в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["qty_t"] is None and "qty_t" in r["missing_fields"] and "qty_integer" in r["hints"]

def test_half_ton():
    r = parse("пол тонны цемента в Карши не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["qty_t"] is None and "qty_integer" in r["hints"]

def test_mixed_language():
    r = parse("200 tonna цемент Наманганга", allow_llm=False)
    assert r["fields"]["qty_t"] == 200 and r["fields"]["region"] == "Namangan"
    assert r["fields"]["commodity"] == "cement" and r["lang"] == "uz"

def test_small_price_assumed_thousands_needs_confirm():
    r = parse("100 тонн цемента в Карши не дороже 950", allow_llm=False)
    assert r["fields"]["max_price_t"] == 950000
    assert "confirm:max_price_t" in r["missing_fields"] and "max_price_t" in r["computed"]

def test_price_conflict():
    r = parse("100 тонн цемента в Карши не дороже 900 тысяч, нет, не дороже 950 тысяч", allow_llm=False)
    assert r["fields"]["max_price_t"] is None and "price_conflict" in r["hints"]

def test_prepay():
    r = parse("100 тонн цемента в Карши, предоплата, не дороже 900 тысяч", allow_llm=False)
    assert r["fields"]["payment_terms"] == "prepay" and "payment_terms" not in r["defaults"]

def test_no_ui_strings_in_codes():
    r = parse("2 мешка цемента М300 Ташкент Карши", allow_llm=False)
    for code in r["missing_fields"] + r["hints"] + [r["confidence_note"]]:
        assert code.isascii(), code
