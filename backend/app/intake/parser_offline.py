from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from . import extract as ex
from .numbers import words_to_digits
from .translit import detect_lang, to_cyrillic

try:
    from app.config import DATA_DEMO
except Exception:  # pragma: no cover
    DATA_DEMO = Path(__file__).resolve().parents[3] / "data" / "demo"

PHRASES_PATH = Path(DATA_DEMO) / "phrases_ru_uz.json"
MAX_TEXT = 5000
SIX_FIELDS = ("commodity", "grade", "qty_t", "region", "deadline", "max_price_t")
REQUIRED = ("commodity", "qty_t", "region", "max_price_t")
DEFAULT_GRADE = "32.5"
DEFAULT_PAYMENT = "after_delivery"
DEFAULT_DEADLINE_DAYS = 7
ACCEPT_MIN_FIELDS = 4

_KEEP = re.compile(r"[^\w\s\-.,%]", re.UNICODE)

def normalize(text: str | None, lang_hint: str | None = None) -> tuple[str, str]:
    raw = unicodedata.normalize("NFC", (text or "")[:MAX_TEXT])
    lang = detect_lang(raw, lang_hint)
    s = to_cyrillic(raw).lower()
    s = s.replace("…", " ").replace("_", " ")
    s = _KEEP.sub(" ", s)
    s = words_to_digits(s, lang)
    s = re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", s)
    s = re.sub(r"(?<![\w])-|-(?![\w])", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s, lang

def match_key(transcript_norm: str) -> str:
    return re.sub(r"[\s\-.,]+", " ", ex.fold(transcript_norm)).strip()

@lru_cache(maxsize=4)
def _load_phrases(path: str) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for item in data.get("phrases", []):
        norm, _ = normalize(item["text"], item.get("lang"))
        out[match_key(norm)] = item
    return out

def phrases() -> list[dict]:
    if not PHRASES_PATH.exists():
        return []
    return json.loads(PHRASES_PATH.read_text(encoding="utf-8")).get("phrases", [])

def lookup_phrase(transcript_norm: str) -> dict | None:
    return _load_phrases(str(PHRASES_PATH)).get(match_key(transcript_norm))

@dataclass
class ParseResult:
    transcript_norm: str
    lang: str
    fields: dict
    missing_fields: list[str] = field(default_factory=list)
    computed: list[str] = field(default_factory=list)
    defaults: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    source: str = "offline"
    matched_phrase: str | None = None

    @property
    def extracted_count(self) -> int:
        return sum(1 for k in SIX_FIELDS if self.fields.get(k) is not None and k not in self.defaults)

    def to_dict(self) -> dict:
        return {
            "transcript_norm": self.transcript_norm,
            "fields": dict(self.fields),
            "missing_fields": list(self.missing_fields),
            "source": self.source,
            "confidence_note": confidence_note(self),
            "lang": self.lang,
            "computed": list(self.computed),
            "defaults": list(self.defaults),
            "hints": list(self.hints),
        }

def confidence_note(r: ParseResult) -> str:
    if not r.transcript_norm:
        return "empty_input"
    if "llm_numbers_dropped" in r.hints:
        return "llm_numbers_dropped"
    if r.missing_fields:
        return "numbers_verified_partial"
    return "numbers_verified"

def _empty_fields() -> dict:
    return {k: None for k in SIX_FIELDS} | {"payment_terms": None}

def finalize(r: ParseResult, today: date | None = None) -> ParseResult:
    today = today or ex.demo_today()
    f = r.fields
    if f.get("grade") is None and "grade" not in r.missing_fields and f.get("commodity") in ("cement", None):
        f["grade"] = DEFAULT_GRADE
        r.defaults.append("grade")
    if f.get("deadline") is None and "deadline" not in r.missing_fields:
        f["deadline"] = (today + timedelta(days=DEFAULT_DEADLINE_DAYS)).isoformat()
        r.defaults.append("deadline")
    if f.get("payment_terms") is None:
        f["payment_terms"] = DEFAULT_PAYMENT
        r.defaults.append("payment_terms")
    for k in REQUIRED:
        if f.get(k) is None and k not in r.missing_fields:
            r.missing_fields.append(k)
    order = {k: i for i, k in enumerate(SIX_FIELDS)}
    r.missing_fields.sort(key=lambda k: (order.get(k.split(":")[-1], 99), k))
    r.hints = list(dict.fromkeys(r.hints))
    r.computed = list(dict.fromkeys(r.computed))
    return r

def parse_rules(transcript_norm: str, lang: str, today: date | None = None) -> ParseResult:
    today = today or ex.demo_today()
    f = ex.fold(transcript_norm)
    r = ParseResult(transcript_norm, lang, _empty_fields())
    if not f or not re.search(r"[^\W\d_]", f):
        return r
    taken = ex.Taken()

    g = ex.extract_grade(f, taken)
    if g.status == "ok":
        r.fields["grade"] = g.value
    elif g.status == "invalid":
        r.missing_fields.append("grade")
        r.blocked.append("grade")
        r.hints.append(g.hint)

    d = ex.extract_deadline(f, today, taken)
    if d.status == "ok":
        r.fields["deadline"] = d.value
    elif d.status in ("past", "invalid"):
        r.missing_fields.append("deadline")
        r.blocked.append("deadline")
        r.hints.append(d.hint)

    q = ex.extract_qty(f, taken)
    if q.status == "ok":
        r.fields["qty_t"] = q.value
        if q.computed:
            r.computed.append("qty_t")
            r.hints.append("qty_from_bags")
    elif q.status in ("conflict", "not_integer"):
        r.missing_fields.append("qty_t")
        r.blocked.append("qty_t")
        r.hints.append(q.hint)

    p = ex.extract_price(f, taken)
    if p.status == "ok":
        r.fields["max_price_t"] = p.value
        if p.computed:
            r.computed.append("max_price_t")
        if p.confirm:
            r.missing_fields.append("confirm:max_price_t")
        r.hints.extend(p.hints)
    elif p.status == "conflict":
        r.missing_fields.append("max_price_t")
        r.blocked.append("max_price_t")
        r.hints.extend(p.hints)

    reg = ex.extract_region(f)
    if reg.status == "ok":
        r.fields["region"] = reg.value
    elif reg.status == "ambiguous":
        r.missing_fields.append("region")
        r.blocked.append("region")
        r.hints.append(reg.hint)

    r.fields["commodity"] = ex.extract_commodity(f)
    if r.fields["commodity"] is None and g.status in ("ok", "invalid"):
        r.fields["commodity"] = "cement"
    r.fields["payment_terms"] = ex.extract_payment(f)
    return r

def from_phrase(item: dict, transcript_norm: str, lang: str) -> ParseResult:
    exp = item["expected"]
    r = ParseResult(
        transcript_norm, lang, _empty_fields() | dict(exp["fields"]),
        missing_fields=list(exp.get("missing_fields", [])),
        computed=list(exp.get("computed", [])),
        defaults=list(exp.get("defaults", [])),
        hints=list(exp.get("hints", [])),
        matched_phrase=item.get("id"),
    )
    return r

def parse_offline(text: str | None, lang_hint: str | None = None, today: date | None = None,
                  use_phrases: bool = True) -> ParseResult:
    transcript_norm, lang = normalize(text, lang_hint)
    if use_phrases and transcript_norm:
        item = lookup_phrase(transcript_norm)
        if item is not None:
            return from_phrase(item, transcript_norm, lang)
    r = parse_rules(transcript_norm, lang, today)
    return finalize(r, today)
