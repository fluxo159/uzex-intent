from __future__ import annotations

MOD = "ʻ"
HARD = "ʼ"

_SIMPLE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ч": "ch", "ш": "sh", "щ": "sh", "ы": "i", "э": "e",
    "ё": "yo", "ю": "yu", "я": "ya", "ъ": HARD, "ь": "",
    "ў": "o" + MOD, "қ": "q", "ғ": "g" + MOD, "ҳ": "h",
}
_VOWELS_CYR = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")
_CYR = set(_SIMPLE) | {"е", "ц"}

def _emit(src_char: str, latin: str, next_char: str) -> str:
    if not src_char.isupper():
        return latin
    if next_char and next_char.isalpha() and next_char.isupper():
        return latin.upper().replace(MOD.upper(), MOD).replace(HARD.upper(), HARD)
    return latin[:1].upper() + latin[1:]

def to_latin(text: str) -> str:
    if not text:
        return text
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        low = ch.lower()
        if low not in _CYR:
            out.append(ch)
            continue
        prev = text[i - 1] if i > 0 else ""
        nxt = text[i + 1] if i + 1 < n else ""
        if low == "е":
            word_start = not prev.isalpha()
            after_vowel = prev in _VOWELS_CYR or prev.lower() in ("ъ", "ь")
            latin = "ye" if (word_start or after_vowel) else "e"
        elif low == "ц":
            between = prev in _VOWELS_CYR and nxt in _VOWELS_CYR
            latin = "ts" if between else "s"
        else:
            latin = _SIMPLE[low]
        out.append(_emit(ch, latin, nxt))
    return "".join(out)

def latinize(obj):
    if isinstance(obj, str):
        return to_latin(obj)
    if isinstance(obj, list):
        return [latinize(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(latinize(x) for x in obj)
    if isinstance(obj, dict):
        return {k: latinize(v) for k, v in obj.items()}
    return obj
