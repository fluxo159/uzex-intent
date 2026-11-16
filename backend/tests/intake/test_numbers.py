import pytest

from app.intake.numbers import parse_number, parse_quantity, words_to_digits
from app.intake.translit import to_cyrillic

@pytest.mark.parametrize("text,value", [
    ("двести", 200),
    ("ikki yuz", 200),
    ("yigirma besh", 25),
    ("1,5 тыс", 1500),
    ("1 млн", 1_000_000),
    ("сто пятьдесят", 150),
    ("девятисот тысяч", 900_000),
    ("полутора миллионов", 1_500_000),
    ("bir yarim million", 1_500_000),
    ("1 миллион 200 минг", 1_200_000),
    ("950 ming", 950_000),
    ("yuz ellik", 150),
    ("ming", 1000),
    ("million", 1_000_000),
    ("1 000 000", 1_000_000),
    ("1,2 млн", 1_200_000),
    ("o'n besh", 15),
    ("qirq", 40),
])
def test_word_numbers(text, value):
    assert parse_number(to_cyrillic(text)) == value

def test_ordinal_day():
    assert words_to_digits("до пятнадцатого") == "до 15"
    assert words_to_digits("до двадцать пятого") == "до 25"

def test_mln_with_tons_not_merged():
    assert words_to_digits("1 млн 200 тонн") == "1000000 200 тонн"

def test_grade_class_kept():
    assert words_to_digits("32,5 триста тонн") == "32.5 300 тонн"

def test_mark_not_touched():
    assert words_to_digits("м400 200 тонн") == "м400 200 тонн"

@pytest.mark.parametrize("text,value", [("200т", 200), ("200 тонн", 200), ("200 tonna", 200), ("сорок тонн", 40)])
def test_tons(text, value):
    q = parse_quantity(text)
    assert q.value == value and q.unit == "t" and not q.computed and not q.rejected

def test_bags_computed():
    q = parse_quantity("2 мешка")
    assert q.value == 0.1 and q.unit == "bag" and q.computed

def test_qop():
    q = parse_quantity("500 qop")
    assert q.value == 25 and q.computed

def test_half_ton_rejected():
    q = parse_quantity("пол тонны")
    assert q.rejected and q.hint == "qty_integer" and q.value == 0.5

def test_conflict():
    q = parse_quantity("20 тонн, нет, 200 тонн")
    assert q.rejected and q.hint == "qty_conflict"
