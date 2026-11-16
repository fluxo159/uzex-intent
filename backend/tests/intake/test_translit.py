import pytest

from app.intake.translit import detect_lang, to_cyrillic

PAIRS = [
    ("oʻzbek", "ўзбек"),
    ("o'zbek", "ўзбек"),
    ("o‘zbek", "ўзбек"),
    ("g'isht", "ғишт"),
    ("gʻisht", "ғишт"),
    ("sement", "семент"),
    ("Qarshi", "Қарши"),
    ("QARSHI", "ҚАРШИ"),
    ("O'zbekiston", "Ўзбекистон"),
    ("Shoshilinch", "Шошилинч"),
    ("choy", "чой"),
    ("Toshkent", "Тошкент"),
    ("Farg'ona", "Фарғона"),
    ("yo'l", "йўл"),
    ("yangi", "янги"),
    ("yuz", "юз"),
    ("ertaga", "эртага"),
    ("mingta", "мингта"),
    ("ma'lumot", "маълумот"),
    ("Namanganga 200 tonna", "Наманганга 200 тонна"),
]

@pytest.mark.parametrize("src,dst", PAIRS)
def test_pairs(src, dst):
    assert to_cyrillic(src) == dst

def test_twenty_pairs():
    assert len(PAIRS) == 20

def test_russian_untouched():
    s = "200 тонн цемента в Наманган"
    assert to_cyrillic(s) == s

def test_mixed_keeps_cyrillic():
    assert to_cyrillic("200 tonna цемент") == "200 тонна цемент"

def test_empty():
    assert to_cyrillic("") == ""

@pytest.mark.parametrize("text,lang", [
    ("200 тонн цемента в Наманган", "ru"),
    ("Наманганга 200 тонна цемент керак", "uz"),
    ("Qarshiga 100 tonna sement", "uz"),
    ("Қаршига 100 тонна", "uz"),
])
def test_detect_lang(text, lang):
    assert detect_lang(text) == lang

def test_hint_wins():
    assert detect_lang("200 тонн", "uz") == "uz"
