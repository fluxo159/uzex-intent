from datetime import date

import httpx
import pytest

from app.intake import extract as ex
from app.intake import parser_llm, parser_offline as po
from app.intake.service import numbers_confirmed, parse

PHRASE = "нужен цемент для стройки в Карши, примерно 150 тонн"

def provider(raw=None, exc=None, calls=None):
    def fn(transcript, timeout):
        if calls is not None:
            calls.append((transcript, timeout))
        if exc is not None:
            raise exc
        return raw
    return fn

@pytest.fixture
def online(monkeypatch):
    monkeypatch.setenv("DEMO_OFFLINE", "0")

def set_providers(monkeypatch, gemini, claude=None):
    monkeypatch.setattr(parser_llm, "PROVIDERS", {"gemini": gemini, "claude": claude or provider(exc=parser_llm.LLMError("x"))})

def test_offline_has_few_fields():
    r = po.parse_rules(*po.normalize(PHRASE))
    assert r.extracted_count < po.ACCEPT_MIN_FIELDS

def test_number_not_in_transcript_goes_missing(monkeypatch, online):
    set_providers(monkeypatch, provider({"commodity": "cement", "qty_value": 150, "price_value": 990000, "region": "Qashqadaryo"}))
    r = parse(PHRASE)
    assert r["fields"]["max_price_t"] is None
    assert "max_price_t" in r["missing_fields"]
    assert "llm_numbers_dropped" in r["hints"] and r["confidence_note"] == "llm_numbers_dropped"
    assert numbers_confirmed(r)

def test_hallucinated_qty_dropped(monkeypatch, online):
    set_providers(monkeypatch, provider({"qty_value": 1500, "price_value": 900000}))
    r = parse("нужен цемент в Карши, не дороже 900 тысяч")
    assert r["fields"]["qty_t"] is None and "qty_t" in r["missing_fields"]
    assert r["fields"]["max_price_t"] == 900000

def test_llm_fills_confirmed_fields(monkeypatch, online):
    set_providers(monkeypatch, provider({"grade_mark": 500, "deadline_day": 20, "deadline_month": 11}))
    r = parse("цемент Карши 150 тонн к 20 числу ноября марка пятисотая", allow_llm=True)
    assert numbers_confirmed(r)

def test_invalid_json_falls_back_to_offline(monkeypatch, online):
    set_providers(monkeypatch, provider(exc=parser_llm.LLMError("bad_json")), provider("not a dict"))
    r = parse(PHRASE)
    assert r["source"] == "offline"
    assert r["fields"]["qty_t"] == 150 and r["fields"]["region"] == "Qashqadaryo"

def test_schema_violation_falls_back(monkeypatch, online):
    set_providers(monkeypatch, provider({"qty_unit": "kg", "qty_value": "много"}))
    r = parse(PHRASE)
    assert r["source"] == "offline"

def test_timeout_falls_back_to_offline(monkeypatch, online):
    set_providers(monkeypatch, provider(exc=httpx.ReadTimeout("t")), provider(exc=httpx.ConnectTimeout("t")))
    r = parse(PHRASE)
    assert r["source"] == "offline" and r["fields"]["qty_t"] == 150

def test_gemini_fails_claude_used(monkeypatch, online):
    calls = []
    set_providers(monkeypatch, provider(exc=httpx.ReadTimeout("t")),
                  provider({"price_value": 150, "price_per": "t"}, calls=calls))
    r = parse("нужен цемент в Карши, примерно 150 тонн, марка 400")
    assert calls == [] and r["source"] == "offline"
    r = parse(PHRASE)
    assert len(calls) == 1 and calls[0][1] <= 8.0

def test_claude_source(monkeypatch, online):
    set_providers(monkeypatch, provider(exc=parser_llm.LLMError("no_key")), provider({"deadline_relative": "urgent"}))
    r = parse(PHRASE)
    assert r["source"] == "claude" and r["fields"]["deadline"] == "2026-11-10"

def test_offline_mode_never_calls(monkeypatch):
    monkeypatch.setenv("DEMO_OFFLINE", "1")
    calls = []
    set_providers(monkeypatch, provider({"price_value": 1}, calls=calls), provider({"price_value": 1}, calls=calls))
    r = parse(PHRASE)
    assert calls == [] and r["source"] == "offline"

def test_cache_reused(monkeypatch, online):
    calls = []
    set_providers(monkeypatch, provider({"deadline_relative": "tomorrow"}, calls=calls))
    a = parse(PHRASE)
    b = parse(PHRASE)
    assert len(calls) == 1 and a == b and a["source"] == "gemini"

def test_cache_used_in_offline_mode(monkeypatch, online):
    set_providers(monkeypatch, provider({"deadline_relative": "tomorrow"}))
    a = parse(PHRASE)
    monkeypatch.setenv("DEMO_OFFLINE", "1")
    set_providers(monkeypatch, provider(exc=AssertionError("must not call")))
    assert parse(PHRASE) == a

def test_llm_cannot_override_conflict(monkeypatch, online):
    set_providers(monkeypatch, provider({"qty_value": 200, "qty_unit": "t"}))
    r = parse("20 тонн… нет, 200 тонн цемента")
    assert r["fields"]["qty_t"] is None and "qty_t" in r["missing_fields"]

def test_month_must_be_said():
    raw = parser_llm.LLMFields(deadline_day=15, deadline_month=1)
    c = parser_llm.convert(raw, "до 15 цемент", date(2026, 11, 8))
    assert c.fields["deadline"] == "2026-11-15"

def test_llm_bags_computed_by_code():
    raw = parser_llm.LLMFields(qty_value=500, qty_unit="bag", price_value=47000, price_per="bag")
    c = parser_llm.convert(raw, "500 қоп цемент қопи 47000 сўмгача", date(2026, 11, 8))
    assert c.fields["qty_t"] == 25 and c.fields["max_price_t"] == 940000
    assert set(c.computed) == {"qty_t", "max_price_t"}

def test_llm_m300_invalid():
    c = parser_llm.convert(parser_llm.LLMFields(grade_mark=300), "цемент м300", date(2026, 11, 8))
    assert "grade" in c.invalid and "grade_options" in c.hints

_REL = [("срочно", "urgent"), ("шошилинч", "urgent"), ("эртага", "tomorrow"), ("завтра", "tomorrow"),
        ("недел", "next_week"), ("хафта", "next_week"), ("конца месяца", "end_of_month"), ("ой охири", "end_of_month")]

def mock_label(item) -> dict:
    e = item["expected"]
    fl = e["fields"]
    norm, _ = po.normalize(item["text"], item["lang"])
    f = ex.fold(norm)
    raw = {"commodity": fl["commodity"], "region": fl["region"], "payment_terms": None}
    if "payment_terms" not in e["defaults"]:
        raw["payment_terms"] = fl["payment_terms"]
    if "grade" not in e["defaults"]:
        mark = {"32.5": 400, "42.5": 500}[fl["grade"]]
        raw["grade_mark" if str(mark) in norm else "grade_class"] = mark if str(mark) in norm else fl["grade"]
    if "qty_t" in e["computed"]:
        raw["qty_value"], raw["qty_unit"] = fl["qty_t"] * 20, "bag"
    else:
        raw["qty_value"], raw["qty_unit"] = fl["qty_t"], "t"
    if fl["max_price_t"] is not None:
        if "max_price_t" in e["computed"]:
            raw["price_value"], raw["price_per"] = fl["max_price_t"] // 20, "bag"
        else:
            raw["price_value"], raw["price_per"] = fl["max_price_t"], "t"
    if "deadline" not in e["defaults"] and fl["deadline"]:
        d = date.fromisoformat(fl["deadline"])
        rel = next((v for k, v in _REL if k in f), None)
        if rel:
            raw["deadline_relative"] = rel
        else:
            raw["deadline_day"] = d.day
            raw["deadline_month"] = d.month if ex._MONTH_DAY.search(f) or ex._DAY_MONTH.search(f) else None
    return raw

@pytest.mark.parametrize("item", po.phrases(), ids=[p["id"] for p in po.phrases()])
def test_i18_online_equals_offline(item):
    norm, _ = po.normalize(item["text"], item["lang"])
    c = parser_llm.convert(parser_llm.LLMFields.model_validate(mock_label(item)), norm, date(2026, 11, 8))
    exp = item["expected"]["fields"]
    for k, v in c.fields.items():
        assert exp[k] == v, (k, v, exp[k])
    for k in ("commodity", "qty_t", "region", "max_price_t"):
        if exp[k] is not None:
            assert c.fields.get(k) == exp[k], k
    assert sorted(c.computed) == sorted(item["expected"]["computed"])

@pytest.mark.parametrize("item", po.phrases(), ids=[p["id"] for p in po.phrases()])
def test_i18_full_parse_online_mode(item, monkeypatch, online):
    set_providers(monkeypatch, provider(mock_label(item)))
    off = parse(item["text"], item["lang"], use_phrases=False, allow_llm=False)
    on = parse(item["text"], item["lang"], use_phrases=False, allow_llm=True)
    assert on["fields"] == off["fields"]
