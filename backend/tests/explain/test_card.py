import json
import re

import pytest
from fastapi.testclient import TestClient

from app.audit import sources
from app.clearing import engine
from app.clearing.models import Ask, Basket, Bid
from app.explain import card, guard
from app.main import app

TARIFF = {("Tashkent_region", "Namangan"): 41_000, ("Tashkent_region", "Andijan"): 60_000,
          ("Tashkent_region", "Tashkent_city"): 10_000}

OTHERS = [
    Bid(mandate_id="SECRET-m2", qty_t=13, max_price_t=777_777, region="Andijan"),
    Bid(mandate_id="SECRET-m3", qty_t=17, max_price_t=888_123, region="Tashkent_city"),
    Bid(mandate_id="SECRET-m4", qty_t=19, max_price_t=654_321, region="Namangan"),
]
ME = Bid(mandate_id="me-1", qty_t=20, max_price_t=1_000_000, region="Namangan")
POOR = Bid(mandate_id="me-poor", qty_t=10, max_price_t=500_000, region="Namangan")
ASK = Ask(offer_id="TC-1", seller="Toshkent Conch Cement", qty_t=300, min_price_t=490_000,
          warehouse_region="Tashkent_region", min_lot_t=1)

def basket(bids, asks=(ASK,)):
    return Basket(basket_id="B-1", bids=list(bids), asks=list(asks))

def run(bids, asks=(ASK,)):
    b = basket(bids, asks)
    return engine.run(b, TARIFF), b

def test_filled_with_delivery():
    res, b = run([ME, *OTHERS])
    c = card.build(res, b, "me-1", "ru", history={"vwap": 480_000})
    assert c["outcome"] == "filled" and c["your_qty"] == 20
    p = res.clearing_price_t
    assert c["your_price_delivered"] == p + 41_000
    assert c["why_in"] == f"ваш потолок 1 000 000 ≥ цена с доставкой {card.fmt(p + 41_000)}"
    assert "Ташкентская область, доставка 41 000 сум/т (демо-тариф)" == c["plant_region"]
    assert c["n_buyers"] == 4 and c["n_plants"] == 1
    assert c["vs_last_week"].endswith("к средней прошлой недели")
    assert c["sentences_uz"] and c["sentences_ru"] != c["sentences_uz"]

def test_unfilled_by_price():
    res, b = run([ME, POOR, *OTHERS])
    c = card.build(res, b, "me-poor", "ru", tariff=TARIFF, next_window="завтра 11:30")
    assert c["outcome"] == "unfilled" and c["reason"] == "price_below_clearing"
    nd = res.clearing_price_t + 41_000
    assert c["why_out"] == f"ваш потолок 500 000 < цена с доставкой {card.fmt(nd)}; ближайшая корзина завтра 11:30"
    assert any("Деньги не списаны" in s for s in c["sentences_ru"])
    cu = card.build(res, b, "me-poor", "uz", next_window={"ru": "завтра 11:30", "uz": "эртага 11:30"})
    assert "ertaga 11:30" in cu["why_out"] and "завтра" not in " ".join(cu["sentences_uz"])
    assert not any(0x0400 <= ord(ch) <= 0x04FF for ch in " ".join(cu["sentences_uz"]))

def test_partial():
    small = Ask(offer_id="TC-1", seller="X", qty_t=25, min_price_t=490_000, warehouse_region="Tashkent_region")
    res, b = run([ME, Bid(mandate_id="other", qty_t=10, max_price_t=1_200_000, region="Namangan",
                          created_at="2025-12-01T00:00:00")], [small])
    c = card.build(res, b, "me-1", "ru")
    assert c["outcome"] == "partial" and c["your_filled_qty"] == 15
    assert any("Исполнено 15 т из 20" in s and "остаток 5 т" in s for s in c["sentences_ru"])

def test_lot_not_formed_text():
    res = {"run_id": "R", "basket_id": "B", "clearing_price_t": None, "allocations": [],
           "unfilled": [{"mandate_id": "me-1", "qty_t": 20, "reason": "lot_not_formed"},
                        {"mandate_id": "x", "qty_t": 15, "reason": "lot_not_formed"}],
           "aggregates": {"total_demand": 35, "total_supply": 300, "n_bids": 2, "n_asks": 1}}
    b = {"bids": [ME.model_dump(), {"mandate_id": "x", "qty_t": 15, "max_price_t": 900_000, "region": "Namangan"}],
         "asks": [{"offer_id": "TC-1", "min_price_t": 490_000, "warehouse_region": "Tashkent_region", "min_lot_t": 50}]}
    c = card.build(res, b, "me-1", "ru")
    assert c["why_out"].startswith("набрано 35 т из 50 нужных заводу, ваше поручение ждёт следующей корзины")

def test_no_cross_no_deal():
    res, b = run([POOR], [Ask(offer_id="A", seller="S", qty_t=10, min_price_t=600_000, warehouse_region="Namangan")])
    c = card.build(res, b, "me-poor", "ru")
    assert c["outcome"] == "unfilled" and c["clearing_price_base"] is None
    assert "предложение от 600 000" in c["why_out"]

def test_no_history_no_vs_last_week():
    res, b = run([ME])
    c = card.build(res, b, "me-1", "ru", history=None)
    assert c["vs_last_week"] is None and not any("прошлой недели" in s for s in c["sentences_ru"])

def test_lang_default_ru():
    res, b = run([ME])
    assert card.build(res, b, "me-1", None)["lang"] == "ru"
    assert card.build(res, b, "me-1", "fr")["lang"] == "ru"

def test_unknown_mandate():
    res, b = run([ME])
    with pytest.raises(KeyError):
        card.build(res, b, "nobody", "ru")

def test_cement_card_has_no_numeric_counterfactual():
    for bids in ([ME, OTHERS[0]], [ME, POOR, *OTHERS]):
        res, b = run(bids)
        for who in [x.mandate_id for x in bids]:
            for lang in ("ru", "uz"):
                c = card.build(res, b, who, lang, tariff=TARIFF)
                txt = json.dumps(c, ensure_ascii=False)
                assert "заплатили бы на" not in txt and "кўп тўлаган" not in txt
                assert "counterfactual_overpay" not in txt
    res, b = run([ME, *OTHERS])
    c = card.build(res, b, "me-1")
    assert c["counterfactual"] == ("Сегодня каждый платил бы свою ставку и гнался за последней секундой. "
                                   f"Здесь одна цена для всех: {card.fmt(res.clearing_price_t)} на складе")

def test_no_deal_no_one_price_sentence():
    res, b = run([POOR], [Ask(offer_id="A", seller="S", qty_t=10, min_price_t=600_000, warehouse_region="Namangan")])
    assert card.build(res, b, "me-poor")["counterfactual"] is None

def _numbers(obj) -> set[int]:
    txt = json.dumps(obj, ensure_ascii=False)
    out = set()
    for m in re.finditer(r"\d[\d ]*", txt):
        out.add(int(m.group(0).replace(" ", "")))
    return out

@pytest.mark.parametrize("who", ["me-1", "me-poor"])
def test_I10_no_foreign_ceilings_qty_or_ids(who):
    res, b = run([ME, POOR, *OTHERS])
    for lang in ("ru", "uz"):
        c = card.build(res, b, who, lang, history={"vwap": 480_000})
        nums = _numbers(c)
        for o in OTHERS:
            assert o.max_price_t not in nums, o.max_price_t
            assert o.qty_t not in nums, o.qty_t
        txt = json.dumps(c, ensure_ascii=False)
        assert "SECRET" not in txt
        other = POOR if who == "me-1" else ME
        assert other.mandate_id not in txt
        if who == "me-poor":
            assert ME.max_price_t not in nums and ME.qty_t not in nums

def test_guard_numbers_and_fallback(monkeypatch):
    s = ["Исполнено 20 т по 571 000 сум/т."]
    assert guard.numbers(s[0]) == guard.numbers("Bajarildi: 20 t, 571 000 so'm/t.")
    monkeypatch.setenv("EXPLAIN_LLM", "1")
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    ok, src = guard.guarded_rephrase(s, "uz", lambda xs, l: ["Bajarildi: 20 t, 571 000 so'm/t."])
    assert src == "llm" and ok[0].startswith("Bajarildi")
    lost, src = guard.guarded_rephrase(s, "uz", lambda xs, l: ["Bajarildi: 20 t."])
    assert src == "template" and lost == s
    changed, src = guard.guarded_rephrase(s, "uz", lambda xs, l: ["Bajarildi: 20 t, 517 000 so'm/t."])
    assert src == "template" and changed == s

    def boom(xs, l):
        raise TimeoutError

    assert guard.guarded_rephrase(s, "uz", boom) == (s, "template")
    assert guard.guarded_rephrase(s, "uz", lambda xs, l: "not a list") == (s, "template")
    monkeypatch.setenv("DEMO_OFFLINE", "1")
    assert guard.guarded_rephrase(s, "uz", lambda xs, l: ["x 20 571 000"])[1] == "template"

def test_card_with_rephrase_end_to_end(monkeypatch):
    monkeypatch.setenv("EXPLAIN_LLM", "1")
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    res, b = run([ME])
    c = card.build(res, b, "me-1", "ru", rephrase=lambda xs, l: [x.replace("1 000 000", "1 000 001") for x in xs])
    assert c["text_source"]["ru"] == "template" and any("1 000 000" in x for x in c["sentences_ru"])

def test_endpoints():
    sources.reset()
    res, b = run([ME, POOR, *OTHERS])
    sources.register_run(res, b, TARIFF)
    cl = TestClient(app)
    j = cl.get("/explain/me-poor", params={"lang": "ru"}).json()
    assert j["outcome"] == "unfilled" and "ближайшая корзина" in j["why_out"]
    assert cl.get("/explain/nobody").status_code == 404
    body = {"result": res.model_dump(mode="json"), "basket": b.model_dump(mode="json"), "mandate_id": "me-1",
            "tariff_rows": [{"from": k[0], "to": k[1], "t": v} for k, v in TARIFF.items()]}
    j = cl.post("/explain", json=body).json()
    assert j["outcome"] == "filled" and "41 000" in j["plant_region"]
    sources.reset()

def test_unfilled_uses_engine_fill_at_price():
    res, b = run([ME, POOR, *OTHERS])
    u = next(x for x in res.unfilled if x.mandate_id == "me-poor")
    c = card.build(res, b, "me-poor", "ru", tariff=TARIFF)
    if u.fill_at_max_price_t is not None:
        assert card.fmt(u.fill_at_max_price_t) in c["why_out"]
