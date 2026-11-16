from __future__ import annotations

import re

from .intake.translit import to_cyrillic

REGIONS = [
    "Andijan", "Bukhara", "Fergana", "Jizzakh", "Khorezm", "Namangan", "Navoiy",
    "Qashqadaryo", "Samarkand", "Sirdaryo", "Surkhandaryo", "Tashkent_region",
    "Tashkent_city", "Karakalpakstan",
]

NAMES = {
    "ru": {
        "Andijan": "Андижан", "Bukhara": "Бухара", "Fergana": "Фергана", "Jizzakh": "Джизак",
        "Khorezm": "Хорезм", "Namangan": "Наманган", "Navoiy": "Навои", "Qashqadaryo": "Карши",
        "Samarkand": "Самарканд", "Sirdaryo": "Сырдарья", "Surkhandaryo": "Термез",
        "Tashkent_region": "Ташкентская обл.", "Tashkent_city": "г. Ташкент",
        "Karakalpakstan": "Нукус",
    },
    "uz": {
        "Andijan": "Андижон", "Bukhara": "Бухоро", "Fergana": "Фарғона", "Jizzakh": "Жиззах",
        "Khorezm": "Хоразм", "Namangan": "Наманган", "Navoiy": "Навоий", "Qashqadaryo": "Қарши",
        "Samarkand": "Самарқанд", "Sirdaryo": "Сирдарё", "Surkhandaryo": "Термиз",
        "Tashkent_region": "Тошкент вилояти", "Tashkent_city": "Тошкент шаҳри",
        "Karakalpakstan": "Нукус",
    },
}

OBLAST_NAMES = {
    "ru": {
        "Andijan": "Андижанская область", "Bukhara": "Бухарская область", "Fergana": "Ферганская область",
        "Jizzakh": "Джизакская область", "Khorezm": "Хорезмская область", "Namangan": "Наманганская область",
        "Navoiy": "Навоийская область", "Qashqadaryo": "Кашкадарьинская область",
        "Samarkand": "Самаркандская область", "Sirdaryo": "Сырдарьинская область",
        "Surkhandaryo": "Сурхандарьинская область", "Tashkent_region": "Ташкентская область",
        "Tashkent_city": "город Ташкент", "Karakalpakstan": "Республика Каракалпакстан",
    },
    "uz": {
        "Andijan": "Андижон вилояти", "Bukhara": "Бухоро вилояти", "Fergana": "Фарғона вилояти",
        "Jizzakh": "Жиззах вилояти", "Khorezm": "Хоразм вилояти", "Namangan": "Наманган вилояти",
        "Navoiy": "Навоий вилояти", "Qashqadaryo": "Қашқадарё вилояти",
        "Samarkand": "Самарқанд вилояти", "Sirdaryo": "Сирдарё вилояти",
        "Surkhandaryo": "Сурхондарё вилояти", "Tashkent_region": "Тошкент вилояти",
        "Tashkent_city": "Тошкент шаҳри", "Karakalpakstan": "Қорақалпоғистон Республикаси",
    },
}

_STEMS: list[tuple[str, str]] = [
    ("каракалпак", "Karakalpakstan"), ("коракалпог", "Karakalpakstan"), ("нукус", "Karakalpakstan"),
    ("наманган", "Namangan"), ("намангон", "Namangan"), ("андиж", "Andijan"),
    ("кашкадар", "Qashqadaryo"), ("карши", "Qashqadaryo"), ("кашкадр", "Qashqadaryo"),
    ("джизак", "Jizzakh"), ("джизз", "Jizzakh"), ("жиззах", "Jizzakh"), ("жизах", "Jizzakh"), ("жиззак", "Jizzakh"),
    ("самарканд", "Samarkand"), ("бухар", "Bukhara"), ("бухоро", "Bukhara"), ("букхар", "Bukhara"),
    ("фергана", "Fergana"), ("фаргона", "Fergana"), ("ферган", "Fergana"), ("коканд", "Fergana"),
    ("кукон", "Fergana"), ("маргилан", "Fergana"),
    ("навои", "Navoiy"), ("навоий", "Navoiy"),
    ("сырдар", "Sirdaryo"), ("сирдар", "Sirdaryo"), ("гулистан", "Sirdaryo"), ("гулистон", "Sirdaryo"),
    ("сурхандар", "Surkhandaryo"), ("сурхондар", "Surkhandaryo"), ("термез", "Surkhandaryo"),
    ("термиз", "Surkhandaryo"),
    ("хорезм", "Khorezm"), ("хоразм", "Khorezm"), ("ургенч", "Khorezm"), ("урганч", "Khorezm"),
    ("чирчик", "Tashkent_region"), ("ангрен", "Tashkent_region"), ("алмалык", "Tashkent_region"),
    ("олмалик", "Tashkent_region"), ("ахангаран", "Tashkent_region"), ("охангарон", "Tashkent_region"),
    ("ташкент", "Tashkent_city"), ("тошкент", "Tashkent_city"),
    ("кхорезм", "Khorezm"), ("сйрдар", "Sirdaryo"), ("суркхандар", "Surkhandaryo"),
    ("суркхондар", "Surkhandaryo"), ("фергхан", "Fergana"), ("самарк", "Samarkand"),
    ("каракалпог", "Karakalpakstan"),
]

_FOLD = str.maketrans({"ё": "е", "ў": "у", "қ": "к", "ғ": "г", "ҳ": "х", "ъ": "", "'": ""})

def fold(text: str) -> str:
    return to_cyrillic(text or "").lower().translate(_FOLD)

_OBL_RE = re.compile(r"(обл|вилоят|viloyat|област)")

def find_regions(text: str) -> list[tuple[int, str]]:
    t = fold(text)
    hits: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for stem, code in _STEMS:
        for m in re.finditer(stem, t):
            a, b = m.start(), m.end()
            if any(a < y and x < b for x, y in taken):
                continue
            if a > 0 and t[a - 1].isalpha():
                continue
            if code == "Tashkent_city":
                tail = t[b:b + 25]
                if _OBL_RE.search(tail) or t[b:b + 4].startswith("ская"):
                    code = "Tashkent_region"
            taken.append((a, b))
            hits.append((a, code))
    hits.sort()
    return hits

def normalize_region(text: str | None) -> str | None:
    if not text:
        return None
    hits = find_regions(text)
    return hits[0][1] if hits else None
