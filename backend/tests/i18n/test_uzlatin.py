import re

import pytest

from app.i18n.uzlatin import HARD, MOD, latinize, to_latin

CYR = re.compile("[Ѐ-ӿ]")

@pytest.mark.parametrize("cyr, lat", [
    ("Бугун ҳар ким ўз нархини тўлар", f"Bugun har kim o{MOD}z narxini to{MOD}lar"),
    ("етказиб бериш", "yetkazib berish"),
    ("сўм/т", f"so{MOD}m/t"),
    ("ҳажмлар демо", "hajmlar demo"),
    ("Цемент", "Sement"),
    ("лицензия", "litsenziya"),
    ("топшириғингиз", f"topshirig{MOD}ingiz"),
    ("Жиззах", "Jizzax"),
    ("шикоят", "shikoyat"),
    ("Қарши", "Qarshi"),
    ("Фарғона", f"Farg{MOD}ona"),
    ("объект", f"ob{HARD}yekt"),
    ("ёғ", f"yog{MOD}"),
    ("кейинги сават", "keyingi savat"),
    ("UZEX реестри 06.11.2026", "UZEX reyestri 06.11.2026"),
])
def test_words(cyr, lat):
    assert to_latin(cyr) == lat

def test_no_cyrillic_left_in_typical_sentence():
    s = "Сизнинг чегарангиз 650 000 ≥ етказиб бериш билан нарх 529 000; навбатдаги сават эртага 11:30"
    out = to_latin(s)
    assert not CYR.search(out)
    assert "650 000" in out and "11:30" in out

def test_caps_word_stays_caps():
    assert to_latin("ДЕМО") == "DEMO"
    assert to_latin("Ўзбекистон") == f"O{MOD}zbekiston"

def test_latin_and_digits_untouched():
    assert to_latin("Toshkent Conch Cement 490 000 sum/t") == "Toshkent Conch Cement 490 000 sum/t"
    assert to_latin("") == ""

def test_latinize_recursive():
    obj = {"a": ["сават", {"b": "нарх"}], "n": 5, "t": ("ҳа",)}
    out = latinize(obj)
    assert out == {"a": ["savat", {"b": "narx"}], "n": 5, "t": ("ha",)}
