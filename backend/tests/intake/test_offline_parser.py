import re
import time

import pytest

from app.intake import parser_offline as po
from app.intake.service import numbers_confirmed, parse

PHRASES = po.phrases()
IDS = [p["id"] for p in PHRASES]
CMP = ("missing_fields", "computed", "defaults", "hints")

def test_thirty_phrases():
    assert len(PHRASES) == 30
    langs = [(p["lang"], p["script"]) for p in PHRASES]
    assert sum(1 for x in langs if x == ("ru", "cyr")) == 10
    assert sum(1 for x in langs if x == ("uz", "cyr")) == 10
    assert sum(1 for x in langs if x[1] in ("lat", "mixed")) == 10

@pytest.mark.parametrize("item", PHRASES, ids=IDS)
def test_rules_match_expected(item):
    r = parse(item["text"], item["lang"], use_phrases=False, allow_llm=False)
    assert r["fields"] == item["expected"]["fields"]
    for k in CMP:
        assert sorted(r[k]) == sorted(item["expected"][k]), k
    assert r["source"] == "offline"

@pytest.mark.parametrize("item", PHRASES, ids=IDS)
def test_exact_match_path(item):
    r = parse(item["text"], item["lang"])
    assert r["fields"] == item["expected"]["fields"]
    assert r["source"] == "offline"
    assert numbers_confirmed(r)

@pytest.mark.parametrize("item", PHRASES, ids=IDS)
def test_exact_match_tolerates_case_and_punct(item):
    noisy = "  " + re.sub(r"(?<!\d),|,(?!\d)", " , ", item["text"].upper()) + "!!! "
    r = parse(noisy, item["lang"])
    assert r["fields"] == item["expected"]["fields"]

def test_response_shape():
    r = parse(PHRASES[0]["text"])
    assert set(r) >= {"transcript_norm", "fields", "missing_fields", "source", "confidence_note"}
    assert set(r["fields"]) == {"commodity", "grade", "qty_t", "region", "deadline", "max_price_t", "payment_terms"}
    assert r["transcript_norm"] == "200 тонн цемента м400 в наманган до 15 ноября не дороже 1000000 за тонну"
    assert r["confidence_note"] == "numbers_verified"

def test_speed_all_phrases_under_300ms():
    for item in PHRASES:
        t0 = time.perf_counter()
        parse(item["text"], use_phrases=False, allow_llm=False)
        assert (time.perf_counter() - t0) < 0.3, item["id"]
