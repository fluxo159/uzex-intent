from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

try:
    from app.config import BAG_KG
except Exception:  # pragma: no cover
    BAG_KG = 50

_FOLD = str.maketrans({"ё": "е", "ў": "у", "қ": "к", "ғ": "г", "ҳ": "х", "ъ": "", "Ё": "е"})

def fold_word(w: str) -> str:
    return w.lower().translate(_FOLD)

VAL: dict[str, Fraction] = {}

def _add(value, *words):
    for w in words:
        VAL[w] = Fraction(value)

_add(0, "ноль", "нуль")
_add(1, "один", "одна", "одну", "одного", "одной", "одно")
_add(2, "два", "две", "двух", "двум")
_add(3, "три", "трех", "трем")
_add(4, "четыре", "четырех", "четырем")
_add(5, "пять", "пяти")
_add(6, "шесть", "шести")
_add(7, "семь", "семи")
_add(8, "восемь", "восьми")
_add(9, "девять", "девяти")
_add(10, "десять", "десяти")
for _v, _w in [(11, "одиннадцат"), (12, "двенадцат"), (13, "тринадцат"), (14, "четырнадцат"),
               (15, "пятнадцат"), (16, "шестнадцат"), (17, "семнадцат"), (18, "восемнадцат"),
               (19, "девятнадцат")]:
    _add(_v, _w + "ь", _w + "и")
_add(20, "двадцать", "двадцати")
_add(30, "тридцать", "тридцати")
_add(40, "сорок", "сорока")
_add(50, "пятьдесят", "пятидесяти")
_add(60, "шестьдесят", "шестидесяти")
_add(70, "семьдесят", "семидесяти")
_add(80, "восемьдесят", "восьмидесяти")
_add(90, "девяносто", "девяноста")
_add(100, "сто", "ста", "сотни", "сотню")
_add(200, "двести", "двухсот")
_add(300, "триста", "трехсот")
_add(400, "четыреста", "четырехсот")
_add(500, "пятьсот", "пятисот")
_add(600, "шестьсот", "шестисот")
_add(700, "семьсот", "семисот")
_add(800, "восемьсот", "восьмисот")
_add(900, "девятьсот", "девятисот")
_add(Fraction(3, 2), "полтора", "полторы", "полутора")
_add(1, "бир")
_add(2, "икки")
_add(3, "уч")
_add(4, "турт")
_add(5, "беш")
_add(6, "олти")
_add(7, "етти")
_add(8, "саккиз")
_add(9, "туккиз")
_add(10, "ун")
_add(20, "йигирма")
_add(30, "уттиз")
_add(40, "кирк")
_add(50, "эллик")
_add(60, "олтмиш")
_add(70, "етмиш")
_add(80, "саксон")
_add(90, "туксон")

UZ_NOAPOS: dict[str, Fraction] = {
    "он": Fraction(10), "торт": Fraction(4), "токкиз": Fraction(9), "токсон": Fraction(90),
    "оттиз": Fraction(30),
}

HALF = {"ярим"}
HUNDRED_MULT = {"юз"}
MULT: dict[str, int] = {}
for _w in ("тысяча", "тысячи", "тысяч", "тысячу", "тысячей", "тыс", "минг"):
    MULT[_w] = 1000
for _w in ("миллион", "миллиона", "миллионов", "миллионом", "млн", "мln"):
    MULT[_w] = 1_000_000
for _w in ("миллиард", "миллиарда", "миллиардов", "млрд"):
    MULT[_w] = 1_000_000_000

_ORD_STEMS = {
    "перв": 1, "втор": 2, "трет": 3, "четверт": 4, "пят": 5, "шест": 6, "седьм": 7, "восьм": 8,
    "девят": 9, "десят": 10, "одиннадцат": 11, "двенадцат": 12, "тринадцат": 13,
    "четырнадцат": 14, "пятнадцат": 15, "шестнадцат": 16, "семнадцат": 17, "восемнадцат": 18,
    "девятнадцат": 19, "двадцат": 20, "тридцат": 30,
}
_ORD_RE = re.compile(
    r"^(" + "|".join(sorted(_ORD_STEMS, key=len, reverse=True)) + r")(ого|его|ьего|ое|ее|ье|ый|ий|ой|ому|ему|ьему|ым|ым)$"
)
_UZ_SUFFIXES = ["инчи", "нчи", "гача", "дан", "нинг", "ни", "га", "та", "лик", "дан"]
_UZ_ORD_SUFFIXES = {"инчи", "нчи"}

@dataclass
class _Tok:
    text: str
    start: int
    end: int
    kind: str = "other"
    value: Fraction | None = None
    suffix: str = ""

def _classify_word(w: str, lang: str | None) -> tuple[str, Fraction | None, str]:
    f = fold_word(w)
    if f in VAL:
        return "val", VAL[f], ""
    if lang == "uz" and f in UZ_NOAPOS:
        return "val", UZ_NOAPOS[f], ""
    if f in MULT:
        return "mult", Fraction(MULT[f]), ""
    if f in HUNDRED_MULT:
        return "hund", Fraction(100), ""
    if f in HALF:
        return "half", Fraction(1, 2), ""
    m = _ORD_RE.match(f)
    if m:
        return "ord", Fraction(_ORD_STEMS[m.group(1)]), ""
    for suf in _UZ_SUFFIXES:
        if f.endswith(suf) and len(f) > len(suf):
            base = f[: -len(suf)]
            kind, val, _ = _classify_word(base, lang) if base != f else ("other", None, "")
            if kind in ("val", "mult", "hund") and val is not None:
                if suf in _UZ_ORD_SUFFIXES:
                    return "ord", val, ""
                return kind, val, suf
    return "other", None, ""

_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*|[^\W\d_]+|\s+|.", re.UNICODE)

def _fmt(v: Fraction) -> str:
    if v.denominator == 1:
        return str(v.numerator)
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return s

def _place(v: Fraction) -> int:
    if v.denominator != 1 or v == 0:
        return 1
    n = v.numerator
    p = 1
    while n % (p * 10) == 0:
        p *= 10
    return p

def _merge_thousand_groups(s: str) -> str:
    s = re.sub(r"(?<![\w.,])(\d{1,3})((?:[    ]\d{3})+)(?![\d])",
               lambda m: m.group(1) + re.sub(r"\D", "", m.group(2)), s)
    s = re.sub(r"(?<![\d.,])(\d{1,3})((?:\.\d{3})+)(?![\d.,])",
               lambda m: m.group(1) + m.group(2).replace(".", ""), s)
    s = re.sub(r"(?<![\d.,])(\d{1,3})((?:,\d{3}){2,})(?![\d.,])",
               lambda m: m.group(1) + m.group(2).replace(",", ""), s)
    return s

def words_to_digits(text: str, lang: str | None = None) -> str:
    if not text:
        return ""
    s = _merge_thousand_groups(text)
    s = re.sub(r"(?i)(?<![^\W\d_])пол\s*-?\s*(?=тонн)", "0.5 ", s)
    s = re.sub(r"(?i)(?<![^\W\d_])пол(?=миллион|млн|тысяч)", "0.5 ", s)
    s = re.sub(r"(\d)([^\W\d_])", r"\1 \2", s)

    toks: list[_Tok] = []
    for m in _TOKEN_RE.finditer(s):
        t = _Tok(m.group(0), m.start(), m.end())
        if t.text.isspace():
            t.kind = "space"
        elif t.text[0].isdigit():
            parts = re.split(r"[.,]", t.text)
            if len(parts) == 2:
                t.kind, t.value = "digit", Fraction(f"{parts[0]}.{parts[1]}")
            elif len(parts) == 1:
                t.kind, t.value = "digit", Fraction(int(parts[0]))
        elif t.text[0].isalpha():
            t.kind, t.value, t.suffix = _classify_word(t.text, lang)
        toks.append(t)

    out: list[str] = []
    i = 0
    n = len(toks)
    numeric = {"digit", "val", "hund", "mult", "half", "ord"}

    def next_numeric(j: int) -> _Tok | None:
        j += 1
        while j < n and toks[j].kind == "space":
            j += 1
        return toks[j] if j < n and toks[j].kind in numeric else None

    while i < n:
        t = toks[i]
        if t.kind not in numeric or (t.kind in ("mult", "hund") and t.text.isdigit()):
            out.append(t.text)
            i += 1
            continue
        total = Fraction(0)
        cur = Fraction(0)
        last_val: Fraction | None = None
        last_mult: Fraction | None = None
        has_any = False
        suffix = ""
        j = i
        end_j = i
        while j < n:
            tk = toks[j]
            if tk.kind == "space":
                j += 1
                continue
            if tk.kind not in numeric:
                break
            ok = True
            if tk.kind == "digit":
                if not has_any:
                    cur = tk.value
                elif cur == 0 and total > 0 and last_mult is not None:
                    nx = next_numeric(j)
                    if nx is not None and nx.kind == "mult" and nx.value < last_mult:
                        cur = tk.value
                    else:
                        ok = False
                else:
                    ok = False
                last_val = tk.value
            elif tk.kind in ("val", "ord"):
                if not has_any:
                    cur = tk.value
                elif cur == 0 and total > 0 and last_mult is not None and tk.value < last_mult:
                    cur = tk.value
                elif cur != 0 and last_val is not None and last_val.denominator == 1 and tk.value < _place(last_val) and last_val >= 10:
                    cur += tk.value
                else:
                    ok = False
                last_val = tk.value
            elif tk.kind == "half":
                if has_any and cur != 0 and cur.denominator == 1:
                    cur += tk.value
                elif not has_any:
                    cur = tk.value
                else:
                    ok = False
            elif tk.kind == "hund":
                if not has_any:
                    cur = Fraction(100)
                elif cur != 0 and cur < 10:
                    cur *= 100
                elif cur == 0 and total > 0:
                    cur = Fraction(100)
                else:
                    ok = False
                last_val = cur
            elif tk.kind == "mult":
                if has_any and last_mult is not None and tk.value >= last_mult and cur == 0:
                    ok = False
                elif has_any and last_mult is not None and tk.value >= last_mult:
                    ok = False
                else:
                    total += (cur if cur != 0 else 1) * tk.value
                    cur = Fraction(0)
                    last_mult = tk.value
                    last_val = tk.value
            if not ok:
                break
            has_any = True
            end_j = j
            suffix = tk.suffix
            j += 1
            if tk.kind == "ord":
                break
        value = total + cur
        out.append(_fmt(value))
        if suffix:
            out.append(" " + suffix)
        i = end_j + 1
    return "".join(out)

def parse_number(text: str, lang: str | None = None) -> float | int | None:
    s = words_to_digits(text, lang)
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    v = Fraction(m.group(0))
    return int(v) if v.denominator == 1 else float(v)

TON_UNIT = r"(?:тонн(?!у\b|ас)[а-я]*|тонна(?!с)[а-я]*|тн|т)"
BAG_UNIT = r"(?:мешк[а-я]*|мешок|меш|коп(?:да|лар|ни)?)"
QTY_RE = re.compile(rf"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:({TON_UNIT})|({BAG_UNIT}))(?![\w])")

@dataclass
class Quantity:
    value: float | int | None
    unit: str | None = None
    raw: str | None = None
    computed: bool = False
    rejected: bool = False
    hint: str | None = None
    all_values: list = field(default_factory=list)

def bags_to_t(n: Fraction) -> Fraction:
    return n * BAG_KG / 1000

def to_num(v: Fraction) -> float | int:
    return int(v) if v.denominator == 1 else float(v)

def parse_quantity(text: str, lang: str | None = None, *, already_normalized: bool = False) -> Quantity:
    from .translit import to_cyrillic

    s = text if already_normalized else words_to_digits(to_cyrillic(text), lang)
    s = fold_word(s)
    found: list[tuple[Fraction, str, str]] = []
    for m in QTY_RE.finditer(s):
        raw = m.group(1)
        n = Fraction(raw)
        unit = "t" if m.group(2) else "bag"
        t = n if unit == "t" else bags_to_t(n)
        found.append((t, unit, raw))
    if not found:
        return Quantity(None)
    distinct = sorted({f[0] for f in found})
    if len(distinct) > 1:
        return Quantity(None, rejected=True, hint="qty_conflict", all_values=[to_num(v) for v in distinct])
    t, unit, raw = found[0]
    q = Quantity(to_num(t), unit=unit, raw=raw, computed=(unit == "bag"), all_values=[to_num(t)])
    if unit == "t" and t.denominator != 1:
        q.rejected, q.hint = True, "qty_integer"
    return q
