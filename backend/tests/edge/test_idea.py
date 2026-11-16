from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.book import store
from app.demo import scenario
from app.main import app

F = dict(commodity="cement", grade="32.5", qty_t=200, region="Namangan", deadline="2026-11-15", max_price_t=1_000_000)
P = {"kind": "ip", "inn": "900000001"}

FORBIDDEN = re.compile(
    r"мандат|коридор|батч|клиринг|стакан|(?<![а-яё])лот(?![а-яё]*_)|оферт|аллокац|\bP[159]0\b"
    r"|\bmandat|kliring|\blot\b|\boferta|alokatsiya", re.I)
NOT_TO_SAY = re.compile(
    r"27\s?%\s?графика|49 из 301|стать[яи] 13 и 17|прогнозир|прогноз цен|точност[ьи] прогноза"
    r"|пункт 70|п\.\s?70\b|согласовано с биржей|ментор одобрил|bashorat", re.I)
OWN_WORDS = {"natural_language_description", "phrase", "display_name", "transcript_norm"}

@pytest.fixture()
def closed():
    out = scenario.reset(2)
    c = TestClient(app)
    run = store.S.runs[out["run_id"]]
    yield c, run
    scenario.reset(1)

def _strings(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, path + (str(k),))
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v, path)
    elif isinstance(o, str):
        yield path, o

def human_texts(obj):
    for path, s in _strings(obj):
        if path and path[-1] in OWN_WORDS:
            continue
        if " " in s or re.search(r"[а-яёʻ]", s, re.I):
            yield ".".join(path), s

def buyer_urls(run):
    mids = [b.mandate_id for b in store.S.run_baskets[run.run_id].bids]
    urls = ["/market/chart", "/market/calendar", "/market/counterfactual/ai92", "/book/tape", "/book/events",
            "/book/ladder", "/book/basket/open", "/clearing/history", "/gate/registry", "/demo/scenario",
            "/health", f"/radar/flags/{run.run_id}"]
    for m in mids:
        urls += [f"/explain/{m}", f"/explain/{m}?lang=uz", f"/escrow/{m}", f"/audit/{m}"]
    return urls

def test_price_is_same_with_llm_flags_on(closed, monkeypatch):
    c, run = closed
    monkeypatch.setenv("EXPLAIN_LLM", "1")
    from app.clearing.delivery import demo_tariff
    from app.clearing.engine import run as engine_run
    again = engine_run(store.S.run_baskets[run.run_id], demo_tariff(), run.reference_price_t)
    assert again.clearing_price_t == run.clearing_price_t and again.allocations == run.allocations

def test_every_number_in_parsed_fields_is_in_the_phrase(closed):
    c, _ = closed
    from app.mandate import validator
    for b in scenario.scenario()["buyers"]:
        d = c.post("/intake/parse", json={"text": b["phrase"], "lang": b["lang"]}).json()
        assert validator.check(d["fields"], d["transcript_norm"], set(d.get("computed", []))) == [], b["key"]

def test_preview_alone_puts_nothing_into_basket():
    scenario.reset(0)
    try:
        c = TestClient(app)
        bid = store.open_basket_id()
        before = c.get(f"/book/basket/{bid}").json()["n_buyers"]
        d = c.post("/mandate/preview", json={"fields": F, "principal": P}).json()
        assert d["mandate_draft"] is not None and d["hash"]
        assert c.get(f"/book/basket/{bid}").json()["n_buyers"] == before
        s = c.post("/mandate/sign", json={"mandate": d["mandate_draft"]}).json()
        assert s["hash"] == d["hash"] and s["receipt"]["hash"] == d["hash"]
        assert c.get(f"/book/basket/{bid}").json()["n_buyers"] == before + 1
    finally:
        scenario.reset(1)

def test_one_price_for_everyone_in_basket(closed):
    c, run = closed
    res = c.get(f"/clearing/result/{run.run_id}").json()
    assert {a["price_t"] for a in res["allocations"]} == {res["clearing_price_t"]}
    bases = {c.get(f"/explain/{a['mandate_id']}").json()["clearing_price_base"] for a in res["allocations"]}
    assert bases == {res["clearing_price_t"]}

def test_small_mandates_pooled_into_plant_lot(closed):
    _, run = closed
    pooled = [g for g in run.lot_groups if g.n_mandates >= 2]
    assert pooled, "в демо хотя бы один лот завода собран из нескольких поручений"
    for g in run.lot_groups:
        assert g.qty_t >= g.min_lot_t

def test_explain_has_no_foreign_ceilings_or_ids(closed):
    c, run = closed
    bids = store.S.run_baskets[run.run_id].bids
    for me in bids:
        for lang in ("ru", "uz"):
            text = json.dumps(c.get(f"/explain/{me.mandate_id}?lang={lang}").json(), ensure_ascii=False)
            compact = re.sub(r"[\s  ]", "", text)
            for other in bids:
                if other.mandate_id == me.mandate_id:
                    continue
                assert other.mandate_id not in text
                if other.max_price_t != me.max_price_t:
                    assert str(other.max_price_t) not in compact, (me.mandate_id, other.max_price_t)

def test_plant_sees_demand_but_no_ceilings(closed):
    c, run = closed
    scenario.reset(1)
    try:
        text = c.get("/plant/Toshkent Conch Cement/demand").text
        for b in store.get_basket(store.open_basket_id()).bids:
            assert str(b.max_price_t) not in text and b.mandate_id not in text
        d = c.get("/plant/Toshkent Conch Cement/demand").json()
        assert d["regions"] and sum(r["qty_t"] for r in d["regions"]) > 0
    finally:
        assert scenario.reset(2)["run_id"] == run.run_id

def test_money_released_only_by_recipient_signature(closed):
    c, run = closed
    mid = sorted({a.mandate_id for a in run.allocations})[-1]
    c.post(f"/escrow/{mid}/event", json={"type": "payment_confirmed"})
    for ev in ("shipped", "payment_confirmed", "timeout"):
        c.post(f"/escrow/{mid}/event", json={"type": ev})
        assert c.get(f"/escrow/{mid}").json()["state"] != "RELEASED", ev
    r = c.post(f"/escrow/{mid}/event", json={"type": "ettn_signed"}).json()
    assert r["escrow"]["state"] == "RELEASED"
    assert r["escrow"]["history"][-2]["event"] == "ettn_signed"

def test_mockups_are_labelled_demo(closed):
    c, run = closed
    mid = run.allocations[0].mandate_id
    assert c.get(f"/escrow/{mid}").json()["demo"] is True
    assert c.get(f"/audit/{mid}").json().get("signer_receipt", {}).get("demo") in (True, None)
    assert c.get("/gate/registry").json()["demo"] is True
    assert c.get(f"/radar/flags/{run.run_id}").json()["demo"] is True
    assert "демо" in c.get("/market/counterfactual/ai92").json()["source_label_ru"]
    scenario.reset(0)
    try:
        d = c.post("/mandate/preview", json={"fields": F, "principal": P}).json()
        assert d["gate"]["demo"] is True
        s = c.post("/mandate/sign", json={"mandate": d["mandate_draft"]}).json()
        assert s["demo"] is True and s["receipt"]["demo"] is True
    finally:
        assert scenario.reset(2)["run_id"] == run.run_id

def test_no_forbidden_words_in_buyer_texts(closed):
    c, run = closed
    bad = []
    for u in buyer_urls(run):
        r = c.get(u)
        assert r.status_code == 200, u
        for path, s in human_texts(r.json()):
            if FORBIDDEN.search(s):
                bad.append((u, path, s[:120]))
    assert bad == []

def test_no_not_to_say_phrases_in_api(closed):
    c, run = closed
    bad = []
    for u in buyer_urls(run) + ["/plant/Toshkent Conch Cement/demand"]:
        for path, s in human_texts(c.get(u).json()):
            if NOT_TO_SAY.search(s):
                bad.append((u, path, s[:120]))
    assert bad == []

I18N = config.ROOT / "frontend" / "src" / "i18n"

@pytest.mark.skipif(not (I18N / "ru.json").exists(), reason="нет фронта рядом")
@pytest.mark.parametrize("lang", ["ru", "uz"])
def test_frontend_strings_have_no_forbidden_or_not_to_say(lang):
    data = json.loads(Path(I18N / f"{lang}.json").read_text(encoding="utf-8"))
    text = {k: re.sub(r"\{[^}]*\}", "", v) for k, v in data.items() if isinstance(v, str)}
    bad = [(k, v) for k, v in text.items() if FORBIDDEN.search(v) or NOT_TO_SAY.search(v)]
    assert bad == []

def test_forbidden_regex_is_not_toothless():
    for s in ("ваш мандат", "коридор цен", "лоты завода", "P50", "kliring", "клиринг", "пункт 70", "AI прогнозирует"):
        assert FORBIDDEN.search(s) or NOT_TO_SAY.search(s), s
    for s in ("поручение", "обычно от 480 000 до 520 000", "партия 50 т", "пилот", "партия", "plot"):
        assert not FORBIDDEN.search(s) and not NOT_TO_SAY.search(s), s
