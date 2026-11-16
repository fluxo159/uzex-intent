from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction

from app import regions as core_regions

from .numbers import BAG_UNIT, QTY_RE, TON_UNIT, bags_to_t, fold_word, to_num

try:
    from app.config import BAG_KG, DEMO_NOW
except Exception:  # pragma: no cover
    BAG_KG, DEMO_NOW = 50, "2026-11-08T10:00:00"

BAGS_PER_T = 1000 // BAG_KG
PRICE_THOUSANDS_BELOW = 1000
PRICE_CONFIRM_BELOW = 100_000
BARE_PRICE_MIN = 100_000

def fold(text: str) -> str:
    return fold_word(text or "").replace("'", "")

def demo_today() -> date:
    try:
        from app import config as _cfg
        if hasattr(_cfg, "now"):
            return _cfg.now().date()
        return datetime.fromisoformat(DEMO_NOW).date()
    except Exception:  # pragma: no cover
        return date(2026, 11, 8)

@dataclass
class Span:
    a: int
    b: int

@dataclass
class Taken:
    spans: list[Span] = field(default_factory=list)

    def add(self, a: int, b: int) -> None:
        self.spans.append(Span(a, b))

    def hit(self, a: int, b: int) -> bool:
        return any(a < s.b and s.a < b for s in self.spans)

_COMMODITY_RE = re.compile(r"(?<![^\W\d_])(цемент|семент|тсемент|sement|cement)")

def extract_commodity(f: str) -> str | None:
    return "cement" if _COMMODITY_RE.search(f) else None

MARK_TO_CLASS = {400: "32.5", 500: "42.5"}
CLASSES = {"32.5", "42.5"}
_MARK_RES = [
    re.compile(r"(?<![^\W\d_])(?:м|m|пц)\s*-?\s*(\d{3})(?!\d)"),
    re.compile(r"(?<![^\W\d_])марк[а-я]*\s*-?\s*(\d{3})(?!\d)"),
    re.compile(r"(?<![\w.])(\d{3})\s*-?\s*(?:марк[а-я]*|маркали)(?![\w])"),
    re.compile(rf"(?<![^\W\d_])(?:цемент|семент)[а-я]*\s+([2-6]00)(?!\d)(?!\s*(?:{TON_UNIT}|{BAG_UNIT})(?![\w]))"),
]
_CLASS_RE = re.compile(r"(?<![\w.])(\d{2})\.(\d)\s*(?:н|р|n|r)?(?![\w.])")

@dataclass
class Grade:
    value: str | None
    status: str
    hint: str | None = None

def extract_grade(f: str, taken: Taken | None = None) -> Grade:
    found: list[str | None] = []
    for rx in _MARK_RES:
        for m in rx.finditer(f):
            if taken is not None and taken.hit(m.start(1), m.end(1)):
                continue
            mark = int(m.group(1))
            found.append(MARK_TO_CLASS.get(mark))
            if taken is not None:
                taken.add(m.start(1), m.end(1))
    for m in _CLASS_RE.finditer(f):
        if taken is not None and taken.hit(m.start(), m.end()):
            continue
        cls = f"{m.group(1)}.{m.group(2)}"
        if m.group(1) in ("22", "32", "42", "52") and m.group(2) == "5":
            found.append(cls if cls in CLASSES else None)
            if taken is not None:
                taken.add(m.start(), m.end())
    if not found:
        return Grade(None, "none")
    valid = {g for g in found if g}
    if None in found and not valid:
        return Grade(None, "invalid", "grade_options")
    if len(valid) > 1:
        return Grade(None, "invalid", "grade_conflict")
    return Grade(valid.pop(), "ok")

EXTRA_STEMS: list[tuple[str, str]] = [
    ("кхорезм", "Khorezm"), ("сйрдар", "Sirdaryo"), ("суркхандар", "Surkhandaryo"),
    ("суркхондар", "Surkhandaryo"), ("фергхан", "Fergana"), ("кашкадр", "Qashqadaryo"),
    ("бухоро", "Bukhara"), ("самарк", "Samarkand"), ("тошкент", "Tashkent_city"),
    ("жиззак", "Jizzakh"), ("навоий", "Navoiy"), ("хоразм", "Khorezm"),
    ("каракалпог", "Karakalpakstan"), ("нукус", "Karakalpakstan"), ("ташкент", "Tashkent_city"),
]
_OBL_TAIL = re.compile(r"^[а-я]*\s*(?:обл|вилоят|област)")

def _stems() -> list[tuple[str, str]]:
    base = list(getattr(core_regions, "_STEMS", []))
    seen = {s for s, _ in base}
    base += [(s, c) for s, c in EXTRA_STEMS if s not in seen]
    return sorted(base, key=lambda p: -len(p[0]))

_STEM_LIST = _stems()

@dataclass
class RegionHit:
    pos: int
    code: str
    word: str
    prev: str

def find_region_hits(f: str) -> list[RegionHit]:
    hits: list[RegionHit] = []
    taken: list[tuple[int, int]] = []
    for stem, code in _STEM_LIST:
        for m in re.finditer(stem, f):
            a = m.start()
            if a > 0 and f[a - 1].isalpha():
                continue
            we = a
            while we < len(f) and f[we].isalpha():
                we += 1
            if any(a < y and x < we for x, y in taken):
                continue
            word = f[a:we]
            c = code
            if c == "Tashkent_city":
                tail = f[a + len(stem):a + len(stem) + 25]
                if _OBL_TAIL.match(tail) or tail.startswith("ск"):
                    c = "Tashkent_region"
            prev_m = re.search(r"([^\W\d_]+)\s*$", f[:a])
            hits.append(RegionHit(a, c, word, prev_m.group(1) if prev_m else ""))
            taken.append((a, we))
    hits.sort(key=lambda h: h.pos)
    return hits

_DEST_PREP = {"в", "во", "на", "до", "к"}
_SRC_PREP = {"из", "с", "со", "от"}

def _is_dest(h: RegionHit, f: str) -> bool:
    if h.prev in _DEST_PREP:
        return True
    if re.search(r"(га|ка|кга)$", h.word):
        return True
    tail = f[h.pos + len(h.word):h.pos + len(h.word) + 20]
    return bool(re.match(r"\s*(шахри|вилояти|области|обл)[а-я]*(га|ка)\b", tail)) or bool(
        re.match(r"\s*(шахрига|вилоятига)", tail))

def _is_src(h: RegionHit) -> bool:
    return h.prev in _SRC_PREP or h.word.endswith("дан")

@dataclass
class Region:
    value: str | None
    status: str
    hint: str | None = None

def extract_region(f: str) -> Region:
    hits = find_region_hits(f)
    if not hits:
        return Region(None, "none")
    codes = {h.code for h in hits}
    if len(codes) == 1:
        return Region(hits[0].code, "ok")
    dest = [h for h in hits if _is_dest(h, f) and not _is_src(h)]
    if dest and len({h.code for h in dest}) == 1:
        return Region(dest[-1].code, "ok")
    non_src = [h for h in hits if not _is_src(h)]
    if len(non_src) < len(hits) and non_src and len({h.code for h in non_src}) == 1:
        return Region(non_src[-1].code, "ok")
    return Region(None, "ambiguous", "region_ambiguous")

_MONTHS = [
    (r"январ|янв", 1), (r"феврал|фев", 2), (r"март", 3), (r"апрел", 4), (r"ма[йяе](?![а-я]{3})", 5),
    (r"июн", 6), (r"июл", 7), (r"август|авг", 8), (r"сентябр|сен", 9), (r"октябр|окт", 10),
    (r"ноябр|ноя", 11), (r"декабр|дек", 12),
]
_MONTH_ALT = "|".join(f"(?:{p})" for p, _ in _MONTHS)

def month_of(word: str) -> int | None:
    for p, n in _MONTHS:
        if re.match(p, word):
            return n
    return None

_DATE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DATE_DOTS = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?![\d.])")
_DAY_MONTH = re.compile(rf"(?<![\w.])(\d{{1,2}})\s*-?\s*(?:е|го|ое|ого|число|числа|си)?\s*-?\s*({_MONTH_ALT})[а-я]*")
_MONTH_DAY = re.compile(rf"(?<![^\W\d_])({_MONTH_ALT})[а-я]*\s+(?:нинг\s+)?(\d{{1,2}})(?:\s*-?\s*(?:си|го|е|числа))?(?![\w.])")
_DAY_ONLY = [
    re.compile(r"(?<![^\W\d_])(?:до|к|по)\s+(\d{1,2})(?:\s*-?\s*(?:го|е|ое|му|числа|число|го\s+числа))?(?![\w.])(?!\s*(?:" + TON_UNIT + "|" + BAG_UNIT + r"|сум|тыс|минг|млн)(?![\w]))"),
    re.compile(r"(?<![\w.])(\d{1,2})\s*-\s*(?:го|е|ое|му|си)?(?:\s*-?\s*)?(?:числа|санагача|сигача|гача|чи|га)?(?![\w])"),
    re.compile(r"(?<![\w.])(\d{1,2})\s*-?\s*(?:гача|сигача|санагача)(?![\w])"),
]
_URGENT = re.compile(r"(?<![^\W\d_])(срочно|срочн[а-я]*|шошилинч[а-я]*|тезда|тез\s+кунда|зудлик|asap)")
_TOMORROW = re.compile(r"(?<![^\W\d_])(завтра|эртага|эртагача)(?![а-я])")
_AFTER_TOMORROW = re.compile(r"(?<![^\W\d_])(послезавтра|индинга)(?![а-я])")
_NEXT_WEEK = re.compile(r"(следующ[а-я]*\s+недел|келаси\s+хафта|кейинги\s+хафта|келаси\s+хафтада)")
_IN_WEEK = re.compile(r"(через\s+неделю|в\s+течение\s+недели|бир\s+хафта(да|\s+ичида)|1\s+хафта(да|\s+ичида)|хафта\s+ичида)")
_IN_DAYS = re.compile(r"(?:через|в\s+течение)\s+(\d{1,2})\s+(?:дн|день|дня|дней)|(\d{1,2})\s+кун\s*(?:да|ичида|ичи|гача)")
_END_MONTH = re.compile(r"(конц[а-я]*\s+месяц|ой\s+охири|ойнинг\s+охири|ой\s+оxири)")
_END_WEEK = re.compile(r"(конц[а-я]*\s+недел|хафта\s+охири)")

@dataclass
class Deadline:
    value: str | None
    status: str
    hint: str | None = None
    source_day: int | None = None

def _nearest_day(day: int, today: date) -> date | None:
    tomorrow = today + timedelta(days=1)
    y, m = tomorrow.year, tomorrow.month
    for _ in range(13):
        if day <= calendar.monthrange(y, m)[1]:
            d = date(y, m, day)
            if d >= tomorrow:
                return d
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return None

def _explicit(day: int, month: int, year: int | None, today: date) -> Deadline:
    y = year or today.year
    if y < 100:
        y += 2000
    try:
        d = date(y, month, day)
    except ValueError:
        return Deadline(None, "invalid", "deadline_invalid")
    if d < today:
        return Deadline(None, "past", "deadline_past", source_day=day)
    return Deadline(d.isoformat(), "ok", source_day=day)

def extract_deadline(f: str, today: date | None = None, taken: Taken | None = None) -> Deadline:
    today = today or demo_today()

    def mark(m: re.Match) -> None:
        if taken is not None:
            taken.add(m.start(), m.end())

    m = _DATE_ISO.search(f)
    if m:
        mark(m)
        return _explicit(int(m.group(3)), int(m.group(2)), int(m.group(1)), today)
    for m in _DATE_DOTS.finditer(f):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12 and (len(m.group(2)) == 2 or m.group(3)):
            mark(m)
            return _explicit(d, mo, int(m.group(3)) if m.group(3) else None, today)
    m = _DAY_MONTH.search(f)
    if m and 1 <= int(m.group(1)) <= 31:
        mark(m)
        return _explicit(int(m.group(1)), month_of(m.group(2)) or 0, None, today)
    m = _MONTH_DAY.search(f)
    if m and 1 <= int(m.group(2)) <= 31:
        mark(m)
        return _explicit(int(m.group(2)), month_of(m.group(1)) or 0, None, today)
    for rx in _DAY_ONLY:
        for m in rx.finditer(f):
            if taken is not None and taken.hit(m.start(1), m.end(1)):
                continue
            day = int(m.group(1))
            if 1 <= day <= 31:
                mark(m)
                d = _nearest_day(day, today)
                return Deadline(d.isoformat() if d else None, "ok" if d else "invalid", source_day=day)
    m = _IN_DAYS.search(f)
    if m:
        mark(m)
        n = int(m.group(1) or m.group(2))
        return Deadline((today + timedelta(days=n)).isoformat(), "ok", source_day=n)
    if _AFTER_TOMORROW.search(f):
        return Deadline((today + timedelta(days=2)).isoformat(), "ok")
    if _URGENT.search(f):
        return Deadline((today + timedelta(days=2)).isoformat(), "ok")
    if _TOMORROW.search(f):
        return Deadline((today + timedelta(days=1)).isoformat(), "ok")
    if _NEXT_WEEK.search(f):
        monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return Deadline(monday.isoformat(), "ok")
    if _IN_WEEK.search(f):
        return Deadline((today + timedelta(days=7)).isoformat(), "ok")
    if _END_MONTH.search(f):
        last = calendar.monthrange(today.year, today.month)[1]
        return Deadline(date(today.year, today.month, last).isoformat(), "ok")
    if _END_WEEK.search(f):
        sunday = today + timedelta(days=(6 - today.weekday()) or 7)
        return Deadline(sunday.isoformat(), "ok")
    return Deadline(None, "none")

@dataclass
class Qty:
    value: int | float | None
    status: str
    computed: bool = False
    hint: str | None = None

_QTY_BEFORE_COMMODITY = re.compile(r"(?<![\w.])(\d+)\s+(?:цемент|семент)")

def extract_qty(f: str, taken: Taken | None = None) -> Qty:
    found: list[tuple[Fraction, str]] = []
    for m in QTY_RE.finditer(f):
        if taken is not None and taken.hit(m.start(1), m.end(1)):
            continue
        before = f[max(0, m.start() - 12):m.start()]
        if m.group(3) and (re.search(r"(?:за|по|за\s+один|за\s+1)\s*$", before)):
            continue
        n = Fraction(m.group(1))
        if m.group(3) and n >= 1000:
            continue
        unit = "t" if m.group(2) else "bag"
        found.append((n if unit == "t" else bags_to_t(n), unit))
        if taken is not None:
            taken.add(m.start(1), m.end(1))
    if not found:
        m = _QTY_BEFORE_COMMODITY.search(f)
        if m and not (taken is not None and taken.hit(m.start(1), m.end(1))) and 0 < int(m.group(1)) < 100_000:
            if taken is not None:
                taken.add(m.start(1), m.end(1))
            return Qty(int(m.group(1)), "ok")
        return Qty(None, "none")
    distinct = {v for v, _ in found}
    if len(distinct) > 1:
        return Qty(None, "conflict", hint="qty_conflict")
    v, unit = found[0]
    if v.denominator != 1 or v < 1:
        return Qty(None, "not_integer", computed=unit == "bag", hint="qty_integer")
    return Qty(to_num(v), "ok", computed=unit == "bag", hint="qty_from_bags" if unit == "bag" else None)

_CEIL_BEFORE = re.compile(
    r"(не\s+дороже|не\s+больше|не\s+выше|дороже\s+не|максимум|макс|потолок|лимит|в\s+пределах|не\s+более|"
    r"до|по|цена|цене|ценой|за\s+тонну|энг\s+купи\s+билан|купи\s+билан|купи|нархи|нарх|тоннаси|тоннасига|"
    r"копи|копига|бахоси|кимматига)\s*$"
)
_CEIL_AFTER = re.compile(
    r"^\s*(сум[а-я]*|сўм[а-я]*|гача|дан\s+ошмасин|дан\s+ошмаслиги|дан\s+оширмай|дан\s+киммат\s+эмас|"
    r"дан\s+ортик\s+эмас|дан|за\s+тонну|за\s+т\b|за\s+мешок|за\s+1\s+т|тоннаси|р\b|руб|uzs|сумов)"
)
_PER_BAG_AFTER = re.compile(r"^\s*(?:сум[а-я]*\s+)?(?:за\s+(?:1\s+|один\s+)?(?:мешок|меш|коп)|за\s+мешок)")
_PER_BAG_BEFORE = re.compile(r"(копи|копига|мешок\s+по|мешок\s+за|мешка\s+по|за\s+мешок)\s*$")
_NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\d])")

@dataclass
class Price:
    value: int | None
    status: str
    computed: bool = False
    confirm: bool = False
    hints: list[str] = field(default_factory=list)

def extract_price(f: str, taken: Taken | None = None) -> Price:
    cands: list[tuple[Fraction, bool, bool, bool]] = []
    for m in _NUM_RE.finditer(f):
        if taken is not None and taken.hit(m.start(1), m.end(1)):
            continue
        v = Fraction(m.group(1))
        before = f[max(0, m.start() - 30):m.start()]
        after = f[m.end():m.end() + 30]
        ctx_b = _CEIL_BEFORE.search(before)
        ctx_a = _CEIL_AFTER.match(after)
        per_bag = bool(_PER_BAG_AFTER.match(after) or _PER_BAG_BEFORE.search(before))
        if ctx_b and not ctx_a and ctx_b.group(1) in ("до", "по") and v <= 31:
            continue
        if ctx_a and ctx_a.group(1) in ("гача", "дан") and not ctx_b and v <= 31:
            continue
        explicit = bool(ctx_b or ctx_a or per_bag)
        if not explicit and v < BARE_PRICE_MIN:
            continue
        cands.append((v, explicit, per_bag, False))
    if not cands:
        return Price(None, "none")
    explicit = [c for c in cands if c[1]] or cands
    distinct = {(c[0], c[2]) for c in explicit}
    if len(distinct) > 1:
        return Price(None, "conflict", hints=["price_conflict"])
    v, _, per_bag, _ = explicit[0]
    hints: list[str] = []
    computed = False
    confirm = False
    if v < PRICE_THOUSANDS_BELOW:
        v = v * 1000
        computed = True
        confirm = True
        hints.append("price_assumed_thousands")
    if per_bag:
        v = v * BAGS_PER_T
        computed = True
        hints.append("price_per_bag")
    if v.denominator != 1:
        v = Fraction(round(v))
    if v < PRICE_CONFIRM_BELOW:
        confirm = True
    return Price(int(v), "ok", computed=computed, confirm=confirm, hints=hints)

_PREPAY = re.compile(r"(предоплат|предварительн[а-я]*\s+оплат|аванс|олдиндан|oldindan|100\s*%\s*вперед)")
_AFTER_DELIVERY = re.compile(r"(после\s+доставки|по\s+факту|постоплат|етказиб\s+берилгандан|етказилгандан|келгандан\s+кейин)")

def extract_payment(f: str) -> str | None:
    if _PREPAY.search(f):
        return "prepay"
    if _AFTER_DELIVERY.search(f):
        return "after_delivery"
    return None
