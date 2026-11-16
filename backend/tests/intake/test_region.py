import pytest

from app.intake import extract as ex
from app.intake.parser_offline import normalize

SPELLINGS = {
    "Andijan": ["Андижан", "Андижон", "Andijon"],
    "Bukhara": ["Бухара", "Бухоро", "Buxoro"],
    "Fergana": ["Фергана", "Фарғона", "Farg'ona"],
    "Jizzakh": ["Джизак", "Жиззах", "Jizzax"],
    "Khorezm": ["Хорезм", "Хоразм", "Xorazm"],
    "Namangan": ["Наманган", "Наманган", "Namangan"],
    "Navoiy": ["Навои", "Навоий", "Navoiy"],
    "Qashqadaryo": ["Кашкадарья", "Қашқадарё", "Qashqadaryo"],
    "Samarkand": ["Самарканд", "Самарқанд", "Samarqand"],
    "Sirdaryo": ["Сырдарья", "Сирдарё", "Sirdaryo"],
    "Surkhandaryo": ["Сурхандарья", "Сурхондарё", "Surxondaryo"],
    "Tashkent_region": ["Ташкентская область", "Тошкент вилояти", "Toshkent viloyati"],
    "Tashkent_city": ["Ташкент", "Тошкент", "Toshkent"],
    "Karakalpakstan": ["Каракалпакстан", "Қорақалпоғистон", "Qoraqalpog'iston"],
}
CASES = [(code, s) for code, ss in SPELLINGS.items() for s in ss]

def region(text):
    n, _ = normalize(text)
    return ex.extract_region(ex.fold(n))

def test_fourteen_codes():
    assert len(SPELLINGS) == 14

@pytest.mark.parametrize("code,text", CASES)
def test_spellings(code, text):
    r = region(text)
    assert r.status == "ok" and r.value == code, text

@pytest.mark.parametrize("text,code", [
    ("Карши", "Qashqadaryo"), ("Qarshi", "Qashqadaryo"), ("Термез", "Surkhandaryo"),
    ("Нукус", "Karakalpakstan"), ("Ургенч", "Khorezm"), ("Коканд", "Fergana"), ("Чирчик", "Tashkent_region"),
    ("в Фергану", "Fergana"), ("в Бухару", "Bukhara"), ("Наманганга", "Namangan"), ("Тошкент шаҳрига", "Tashkent_city"),
])
def test_city_to_region(text, code):
    assert region(text).value == code

def test_from_to():
    r = region("из Ташкента в Карши")
    assert r.value == "Qashqadaryo"

def test_from_to_uz():
    assert region("Тошкентдан Қаршига").value == "Qashqadaryo"

def test_two_regions_without_preposition():
    r = region("Ташкент Карши")
    assert r.value is None and r.status == "ambiguous" and r.hint == "region_ambiguous"

def test_none():
    assert region("200 тонн цемента").status == "none"
