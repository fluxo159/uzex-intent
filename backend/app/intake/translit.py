from __future__ import annotations

import re
import unicodedata

APOS = "'ʻʼ’‘`´"
_APOS_RE = re.compile(f"[{re.escape(APOS)}]")

_TRIGRAPHS = [("yo'", "йў"), ("yu'", "йў")]
_DIGRAPHS = [
    ("o'", "ў"), ("g'", "ғ"), ("sh", "ш"), ("ch", "ч"),
    ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ye", "е"),
]
_SINGLE = {
    "a": "а", "b": "б", "c": "с", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "х",
    "y": "й", "z": "з",
}

_UZ_CYR_LETTERS = set("ўқғҳЎҚҒҲ")
_UZ_MARKERS = re.compile(
    r"(гача\b|\bкерак|\bтонна\b|\bтоннаси|\bсўм|\bминг\b|\bюз\b|\bикки\b|\bқоп|\bҳафта|\bэртага|"
    r"\bшошилинч|\bошмасин|\bбилан\b|\bвилоят|\bшаҳр|га\b)",
    re.IGNORECASE,
)
_RU_MARKERS = re.compile(
    r"(\bтонн\b|\bнужн|\bнужен|\bдороже|\bбольше|\bмаксимум|\bцемента\b|\bдо\b|\bмешк|\bсрочно|"
    r"\bнедел|ы|щ|ь)",
    re.IGNORECASE,
)

def _case(src: str, dst: str) -> str:
    return dst.upper() if src[:1].isupper() else dst

def to_cyrillic(text: str) -> str:
    if not text:
        return ""
    s = _APOS_RE.sub("'", unicodedata.normalize("NFC", text))
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        low3 = s[i:i + 3].lower()
        hit = next((p for p in _TRIGRAPHS if low3 == p[0]), None)
        if hit:
            first, second = hit[1][0], hit[1][1]
            out.append(_case(s[i], first))
            out.append(second.upper() if s[i + 1].isupper() else second)
            i += 3
            continue
        low2 = s[i:i + 2].lower()
        hit = next((p for p in _DIGRAPHS if low2 == p[0]), None)
        if hit and ch.isascii():
            out.append(_case(s[i], hit[1]))
            i += 2
            continue
        lo = ch.lower()
        if lo in _SINGLE and ch.isascii():
            prev = s[i - 1] if i > 0 else " "
            word_start = not prev.isalpha()
            dst = "э" if (lo == "e" and word_start) else _SINGLE[lo]
            out.append(_case(ch, dst))
        elif ch == "'":
            prev = s[i - 1] if i > 0 else " "
            nxt = s[i + 1] if i + 1 < n else " "
            out.append("ъ" if prev.isalpha() and nxt.isalpha() else ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)

def script_stats(text: str) -> tuple[int, int]:
    lat = cyr = 0
    for ch in text or "":
        if not ch.isalpha():
            continue
        if ch.isascii():
            lat += 1
        elif "Ѐ" <= ch <= "ӿ":
            cyr += 1
    return lat, cyr

def detect_lang(text: str, hint: str | None = None) -> str:
    if hint in ("ru", "uz"):
        return hint
    lat, cyr = script_stats(text)
    if lat == 0 and cyr == 0:
        return "ru"
    if any(ch in _UZ_CYR_LETTERS for ch in text):
        return "uz"
    cyr_text = to_cyrillic(text)
    uz = len(_UZ_MARKERS.findall(cyr_text))
    ru = len(_RU_MARKERS.findall(text)) if cyr else 0
    if lat > cyr:
        return "uz" if uz >= ru else "ru"
    return "uz" if uz > ru else "ru"
