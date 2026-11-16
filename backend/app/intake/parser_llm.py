from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app import regions as core_regions

from . import extract as ex

try:
    from app import config as _cfg
    LLM_TIMEOUT_S = float(getattr(_cfg, "LLM_TIMEOUT_S", 8.0))
    ROOT = Path(_cfg.ROOT)
    offline = _cfg.offline
except Exception:  # pragma: no cover
    LLM_TIMEOUT_S = 8.0
    ROOT = Path(__file__).resolve().parents[3]

    def offline() -> bool:
        return os.environ.get("DEMO_OFFLINE", "0") == "1"

PROMPT_VERSION = "intake-llm-1"
CACHE_DIR = ROOT / "data" / "cache" / "intake"
GEMINI_SHARE = 0.6
REGION_CODES = list(core_regions.REGIONS)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
OPENAI_MODEL_FALLBACK = os.environ.get("OPENAI_MODEL_FALLBACK", "gpt-4o-mini")

SYSTEM = (
    "You label a buyer's order phrase for a commodity exchange (Russian or Uzbek, already normalized: "
    "numbers are digits). Extract ONLY what is literally said. Do not compute, convert, round or guess. "
    "Copy numbers exactly as they appear in the text. If a field is not said, return null. "
    "grade_mark: the cement mark number as said (М400 -> 400). grade_class: '32.5' or '42.5' only if the class "
    "itself is said. qty_value + qty_unit ('t' tons or 'bag' bags/мешок/қоп). region: destination region code. "
    "deadline_day/deadline_month: only if a day number is said; deadline_relative: urgent (срочно/шошилинч), "
    "tomorrow (завтра/эртага), next_week, in_week (через неделю), end_of_month. price_value: the ceiling price "
    "number as said; price_per: 't' per ton or 'bag' per bag. payment_terms: prepay or after_delivery if said."
)

class LLMFields(BaseModel):
    model_config = ConfigDict(extra="ignore")
    commodity: Optional[Literal["cement"]] = None
    grade_mark: Optional[int] = None
    grade_class: Optional[str] = None
    qty_value: Optional[float] = None
    qty_unit: Optional[Literal["t", "bag"]] = None
    region: Optional[str] = None
    deadline_day: Optional[int] = None
    deadline_month: Optional[int] = None
    deadline_relative: Optional[Literal["urgent", "tomorrow", "next_week", "in_week", "end_of_month"]] = None
    price_value: Optional[float] = None
    price_per: Optional[Literal["t", "bag"]] = None
    payment_terms: Optional[Literal["after_delivery", "prepay"]] = None

def json_schema() -> dict:
    def n(t, **kw):
        return {"type": [t, "null"], **kw}
    return {
        "type": "object",
        "properties": {
            "commodity": n("string", enum=["cement", None]),
            "grade_mark": n("integer"),
            "grade_class": n("string"),
            "qty_value": n("number"),
            "qty_unit": n("string", enum=["t", "bag", None]),
            "region": n("string", enum=REGION_CODES + [None]),
            "deadline_day": n("integer"),
            "deadline_month": n("integer"),
            "deadline_relative": n("string", enum=["urgent", "tomorrow", "next_week", "in_week", "end_of_month", None]),
            "price_value": n("number"),
            "price_per": n("string", enum=["t", "bag", None]),
            "payment_terms": n("string", enum=["after_delivery", "prepay", None]),
        },
        "required": [],
        "additionalProperties": False,
    }

def gemini_schema() -> dict:
    def n(t, **kw):
        return {"type": t, "nullable": True, **kw}
    return {
        "type": "OBJECT",
        "properties": {
            "commodity": n("STRING", enum=["cement"]),
            "grade_mark": n("INTEGER"),
            "grade_class": n("STRING"),
            "qty_value": n("NUMBER"),
            "qty_unit": n("STRING", enum=["t", "bag"]),
            "region": n("STRING", enum=REGION_CODES),
            "deadline_day": n("INTEGER"),
            "deadline_month": n("INTEGER"),
            "deadline_relative": n("STRING", enum=["urgent", "tomorrow", "next_week", "in_week", "end_of_month"]),
            "price_value": n("NUMBER"),
            "price_per": n("STRING", enum=["t", "bag"]),
            "payment_terms": n("STRING", enum=["after_delivery", "prepay"]),
        },
    }

class LLMError(Exception):
    pass

def call_gemini(transcript_norm: str, timeout: float) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise LLMError("no_key")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": transcript_norm}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema(),
        },
    }
    r = httpx.post(url, json=body, headers={"x-goog-api-key": key}, timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"http_{r.status_code}")
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise LLMError("bad_json") from e

def call_claude(transcript_norm: str, timeout: float) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise LLMError("no_key")
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 400,
        "system": SYSTEM,
        "tools": [{"name": "emit_fields", "description": "Return the labeled fields.", "input_schema": json_schema()}],
        "tool_choice": {"type": "tool", "name": "emit_fields"},
        "messages": [{"role": "user", "content": transcript_norm}],
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    r = httpx.post("https://api.anthropic.com/v1/messages", json=body, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"http_{r.status_code}")
    try:
        for block in r.json()["content"]:
            if block.get("type") == "tool_use":
                return block["input"]
    except (KeyError, ValueError, TypeError) as e:
        raise LLMError("bad_json") from e
    raise LLMError("bad_json")

def call_openai(transcript_norm: str, timeout: float) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise LLMError("no_key")
    schema = json_schema()
    body = {
        "model": OPENAI_MODEL,
        "temperature": 0,
        "max_tokens": 400,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": transcript_norm}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "emit_fields", "schema": schema, "strict": False}},
    }
    headers = {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    r = httpx.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=timeout)
    if r.status_code == 400 and OPENAI_MODEL_FALLBACK and body["model"] != OPENAI_MODEL_FALLBACK:
        body["model"] = OPENAI_MODEL_FALLBACK
        r = httpx.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"http_{r.status_code}")
    try:
        text = r.json()["choices"][0]["message"]["content"]
        return json.loads(text)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise LLMError("bad_json") from e

PROVIDERS: dict = {"openai": call_openai, "gemini": call_gemini, "claude": call_claude}

def _order() -> tuple[str, ...]:
    keys = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}
    have = [n for n in ("openai", "gemini", "claude") if os.environ.get(keys[n], "").strip()]
    rest = [n for n in ("gemini", "claude", "openai") if n not in have]
    return tuple(have + rest)

ORDER = ("gemini", "claude")

def _effective_order() -> tuple[str, ...]:
    keys = ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
    return _order() if any(os.environ.get(k, "").strip() for k in keys) else ORDER

def _cache_path(transcript_norm: str) -> Path:
    h = hashlib.sha256(f"{PROMPT_VERSION}|{transcript_norm}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.json"

def cache_get(transcript_norm: str) -> tuple[str, dict] | None:
    p = _cache_path(transcript_norm)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d["provider"], d["raw"]
    except Exception:
        return None

def cache_put(transcript_norm: str, provider: str, raw: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(transcript_norm).write_text(
            json.dumps({"provider": provider, "raw": raw, "transcript_norm": transcript_norm,
                        "prompt": PROMPT_VERSION}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

_attempt = threading.local()

def take_attempted() -> bool:
    v = getattr(_attempt, "flag", False)
    _attempt.flag = False
    return v

def llm_extract(transcript_norm: str, budget: float | None = None) -> tuple[str, LLMFields] | None:
    if not transcript_norm:
        return None
    hit = cache_get(transcript_norm)
    if hit is not None:
        try:
            return hit[0], LLMFields.model_validate(hit[1])
        except ValidationError:
            pass
    if offline():
        return None
    budget = LLM_TIMEOUT_S if budget is None else budget
    t0 = time.monotonic()
    order = _effective_order()
    for i, name in enumerate(order):
        left = budget - (time.monotonic() - t0)
        if left <= 0.2:
            break
        timeout = left * GEMINI_SHARE if i == 0 and len(order) > 1 else left
        fn = PROVIDERS.get(name)
        if fn is None:
            continue
        _attempt.flag = True
        try:
            raw = fn(transcript_norm, timeout)
            if not isinstance(raw, dict):
                raise LLMError("bad_json")
            parsed = LLMFields.model_validate(raw)
        except (LLMError, ValidationError, httpx.HTTPError, ValueError, TypeError, KeyError):
            continue
        cache_put(transcript_norm, name, parsed.model_dump())
        return name, parsed
    return None

def transcript_numbers(transcript_norm: str) -> set[Fraction]:
    return {Fraction(x) for x in re.findall(r"\d+(?:\.\d+)?", transcript_norm or "")}

def _in_transcript(v, nums: set[Fraction]) -> bool:
    try:
        return Fraction(str(v)) in nums
    except (ValueError, ZeroDivisionError):
        return False

@dataclass
class Converted:
    fields: dict = field(default_factory=dict)
    computed: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    confirm: list[str] = field(default_factory=list)

def convert(raw: LLMFields, transcript_norm: str, today: date | None = None) -> Converted:
    today = today or ex.demo_today()
    nums = transcript_numbers(transcript_norm)
    f = ex.fold(transcript_norm)
    c = Converted()

    if raw.commodity == "cement" and ex.extract_commodity(f):
        c.fields["commodity"] = "cement"

    if raw.grade_mark is not None:
        if _in_transcript(raw.grade_mark, nums):
            g = ex.MARK_TO_CLASS.get(raw.grade_mark)
            if g:
                c.fields["grade"] = g
            else:
                c.invalid.append("grade")
                c.hints.append("grade_options")
        else:
            c.dropped.append("grade")
    elif raw.grade_class is not None:
        cls = raw.grade_class.replace(",", ".").strip()
        if _in_transcript(cls, nums) and cls in ex.CLASSES:
            c.fields["grade"] = cls
        else:
            c.dropped.append("grade")
    if "grade" in c.fields and "commodity" not in c.fields:
        c.fields["commodity"] = "cement"

    if raw.qty_value is not None:
        if _in_transcript(raw.qty_value, nums):
            n = Fraction(str(raw.qty_value))
            t = ex.bags_to_t(n) if raw.qty_unit == "bag" else n
            if t.denominator != 1 or t < 1:
                c.invalid.append("qty_t")
                c.hints.append("qty_integer")
            else:
                c.fields["qty_t"] = int(t)
                if raw.qty_unit == "bag":
                    c.computed.append("qty_t")
                    c.hints.append("qty_from_bags")
        else:
            c.dropped.append("qty_t")

    if raw.region in REGION_CODES:
        c.fields["region"] = raw.region

    if raw.deadline_day is not None:
        if _in_transcript(raw.deadline_day, nums) and 1 <= raw.deadline_day <= 31:
            month = raw.deadline_month
            said = {ex.month_of(w) for w in re.findall(r"[а-я]+", f)} - {None}
            if month is not None and (month in said or _in_transcript(month, nums)):
                d = ex._explicit(raw.deadline_day, month, None, today)
            else:
                nd = ex._nearest_day(raw.deadline_day, today)
                d = ex.Deadline(nd.isoformat() if nd else None, "ok" if nd else "invalid")
            if d.status == "ok":
                c.fields["deadline"] = d.value
            else:
                c.invalid.append("deadline")
                if d.hint:
                    c.hints.append(d.hint)
        else:
            c.dropped.append("deadline")
    elif raw.deadline_relative:
        rel = {"urgent": "срочно", "tomorrow": "завтра", "next_week": "следующей неделе",
               "in_week": "через неделю", "end_of_month": "конца месяца"}[raw.deadline_relative]
        d = ex.extract_deadline(ex.fold(rel if rel != "следующей неделе" else "на следующей неделе"), today)
        if d.status == "ok":
            c.fields["deadline"] = d.value

    if raw.price_value is not None:
        if _in_transcript(raw.price_value, nums):
            v = Fraction(str(raw.price_value))
            computed = False
            if v < ex.PRICE_THOUSANDS_BELOW:
                v *= 1000
                computed = True
                c.confirm.append("confirm:max_price_t")
                c.hints.append("price_assumed_thousands")
            if raw.price_per == "bag":
                v *= ex.BAGS_PER_T
                computed = True
                c.hints.append("price_per_bag")
            if v < ex.PRICE_CONFIRM_BELOW and "confirm:max_price_t" not in c.confirm:
                c.confirm.append("confirm:max_price_t")
            c.fields["max_price_t"] = int(round(v))
            if computed:
                c.computed.append("max_price_t")
        else:
            c.dropped.append("max_price_t")

    if raw.payment_terms:
        c.fields["payment_terms"] = raw.payment_terms
    return c
