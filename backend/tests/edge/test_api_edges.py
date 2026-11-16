from __future__ import annotations

import concurrent.futures as cf
import re

import pytest
from fastapi.testclient import TestClient

from app.book import store
from app.demo import scenario
from app.main import app

F = dict(commodity="cement", grade="32.5", qty_t=200, region="Namangan", deadline="2026-11-15", max_price_t=1_000_000)
P = {"kind": "ip", "inn": "900000001"}
CYR = re.compile(r"[а-яё]", re.I)

@pytest.fixture()
def c():
    scenario.reset(0)
    yield TestClient(app, raise_server_exceptions=False)
    scenario.reset(1)

def human(r) -> str:
    d = r.json().get("detail")
    if isinstance(d, dict):
        d = d.get("code") or d.get("message") or ""
    return d if isinstance(d, str) else ""

def preview(c, **kw):
    r = c.post("/mandate/preview", json={"fields": {**F, **kw}, "principal": P})
    assert r.status_code == 200, r.text
    return r.json()

def sign(c, **kw):
    d = preview(c, **kw)
    assert d["mandate_draft"] is not None, d["errors"]
    r = c.post("/mandate/sign", json={"mandate": d["mandate_draft"]})
    assert r.status_code == 200, r.text
    return r.json()

def codes(d, key="errors"):
    return {e["code"] for e in d[key]}

def test_parse_empty_string_is_all_missing_not_500(c):
    r = c.post("/intake/parse", json={"text": ""})
    assert r.status_code == 200
    d = r.json()
    assert set(d["missing_fields"]) >= {"commodity", "qty_t", "region", "max_price_t"}
    assert d["confidence_note"] == "empty_input"

def test_parse_null_text_is_same_as_empty(c):
    r = c.post("/intake/parse", json={"text": None})
    assert r.status_code == 200 and r.json()["confidence_note"] == "empty_input"

def test_parse_whitespace_and_emoji_only(c):
    for t in ("   \n\t ", "🙂🙂🙂", "!!!???"):
        r = c.post("/intake/parse", json={"text": t})
        assert r.status_code == 200, t
        assert r.json()["fields"]["qty_t"] is None

def test_parse_only_digits_is_all_missing(c):
    d = c.post("/intake/parse", json={"text": "123 456"}).json()
    assert d["fields"]["commodity"] is None and d["fields"]["region"] is None

def test_parse_5000_chars_answers_without_500(c):
    text = ("200 тонн цемента в Наманган не дороже 1000000 " * 120)[:5000]
    assert len(text) == 5000
    r = c.post("/intake/parse", json={"text": text})
    assert r.status_code == 200
    assert r.json()["fields"]["region"] == "Namangan"

def test_parse_negative_tonnes_never_yields_negative_qty(c):
    d = c.post("/intake/parse", json={"text": "-200 тонн цемента наманган не дороже 1000000"}).json()
    q = d["fields"]["qty_t"]
    assert q is None or q >= 1

def test_parse_two_regions_with_preposition_takes_destination(c):
    d = c.post("/intake/parse", json={"text": "200 тонн цемента из Ташкента в Карши не дороже 900000"}).json()
    assert d["fields"]["region"] == "Qashqadaryo"

def test_parse_two_regions_without_preposition_is_missing(c):
    d = c.post("/intake/parse", json={"text": "200 тонн цемента Ташкент Карши не дороже 900000"}).json()
    assert d["fields"]["region"] is None and "region" in d["missing_fields"]

def test_parse_nonexistent_grade_m300_is_missing_with_hint(c):
    d = c.post("/intake/parse", json={"text": "200 тонн цемента м300 наманган не дороже 900000"}).json()
    assert d["fields"]["grade"] is None and "grade" in d["missing_fields"]
    assert "grade_options" in d["hints"]

def test_parse_past_deadline_is_flagged(c):
    d = c.post("/intake/parse", json={"text": "200 тонн цемента наманган до 1 ноября 2026 не дороже 900000"}).json()
    assert d["fields"]["deadline"] is None
    assert "deadline" in d["missing_fields"]

def test_parse_wrong_type_text_is_4xx(c):
    r = c.post("/intake/parse", json={"text": {"a": 1}})
    assert 400 <= r.status_code < 500

def test_preview_negative_qty_is_error_no_draft(c):
    d = preview(c, qty_t=-5)
    assert "qty_not_positive" in codes(d) and d["mandate_draft"] is None

def test_preview_zero_qty_is_error_no_draft(c):
    d = preview(c, qty_t=0)
    assert "qty_not_positive" in codes(d) and d["mandate_draft"] is None

def test_preview_fractional_qty_rejected_by_schema(c):
    r = c.post("/mandate/preview", json={"fields": {**F, "qty_t": 2.5}, "principal": P})
    assert r.status_code == 422

def test_preview_text_qty_rejected_by_schema(c):
    r = c.post("/mandate/preview", json={"fields": {**F, "qty_t": "двести"}, "principal": P})
    assert r.status_code == 422

def test_preview_ceiling_one_sum_is_warning_not_ban(c):
    d = preview(c, max_price_t=1)
    assert "price_far_from_market" in codes(d, "warnings")
    assert d["mandate_draft"] is not None
    assert d["fees"]["gross_max"] == 200 and d["fees"]["exchange_fee"] == 0

def test_preview_ceiling_zero_is_error(c):
    d = preview(c, max_price_t=0)
    assert "price_not_positive" in codes(d) and d["mandate_draft"] is None

def test_preview_ceiling_billion_counts_exactly_and_gate_blocks_on_money(c):
    d = preview(c, max_price_t=10**9)
    assert d["fees"]["gross_max"] == 200 * 10**9
    assert d["fees"]["exchange_fee"] == 403_200_000
    assert d["fees"]["deposit_worst"] == 20 * 10**9
    assert d["gate"]["status"] == "blocked" and "gate_blocked" in codes(d)
    funds = next(ch for ch in d["gate"]["checks"] if ch["name"] == "funds")
    assert CYR.search(funds["reason"]) and funds["how_to_fix"]

def test_preview_huge_numbers_no_overflow(c):
    d = preview(c, qty_t=10**9, max_price_t=10**18)
    assert d["fees"]["gross_max"] == 10**27
    assert d["mandate_draft"] is None

def test_preview_deadline_in_past_is_error(c):
    d = preview(c, deadline="2026-11-01")
    assert "deadline_past" in codes(d) and d["mandate_draft"] is None

def test_preview_deadline_today_warns_before_next_basket(c):
    d = preview(c, deadline="2026-11-08")
    assert "deadline_before_next_basket" in codes(d, "warnings")

def test_preview_unknown_grade_is_4xx(c):
    r = c.post("/mandate/preview", json={"fields": {**F, "grade": "30.0"}, "principal": P})
    assert r.status_code == 422

def test_preview_unknown_commodity_is_4xx(c):
    r = c.post("/mandate/preview", json={"fields": {**F, "commodity": "gold"}, "principal": P})
    assert r.status_code == 422

def test_preview_missing_required_fields_named(c):
    r = c.post("/mandate/preview", json={"fields": {"commodity": "cement"}, "principal": P})
    d = r.json()
    missing = {e["params"].get("field") for e in d["errors"] if e["code"] == "missing"}
    assert missing == {"qty_t", "region", "max_price_t"} and d["mandate_draft"] is None

def test_preview_unknown_region_is_error(c):
    d = preview(c, region="Mars")
    assert d["mandate_draft"] is None

def test_preview_empty_region_is_missing(c):
    d = preview(c, region="")
    assert d["mandate_draft"] is None

def test_preview_blocked_company_not_found(c):
    r = c.post("/mandate/preview", json={"fields": F, "principal": {"kind": "company", "inn": "000000000"}})
    d = r.json()
    assert d["gate"]["status"] == "blocked" and d["mandate_draft"] is None
    bad = [ch for ch in d["gate"]["checks"] if not ch["passed"]]
    assert bad and all(CYR.search(ch["reason"]) for ch in bad)

def test_sign_puts_mandate_into_open_basket(c):
    s = sign(c)
    assert s["basket_id"] == store.open_basket_id()
    assert s["mandate_id"] in store.S.baskets[s["basket_id"]].mandate_ids

def test_sign_same_mandate_twice_is_idempotent(c):
    d = preview(c)
    r1 = c.post("/mandate/sign", json={"mandate": d["mandate_draft"]})
    r2 = c.post("/mandate/sign", json={"mandate": d["mandate_draft"]})
    assert r1.status_code == 200
    assert r2.status_code in (200, 409)
    bid = store.open_basket_id()
    assert c.get(f"/book/basket/{bid}").json()["demand_t"] == 200

def test_sign_twice_never_500_and_ids_unique(c):
    d = preview(c)
    ids = {c.post("/mandate/sign", json={"mandate": d["mandate_draft"]}).json()["mandate_id"] for _ in range(3)}
    assert len(ids) == 1

def test_sign_forged_mandate_id_is_replaced_by_hash_id(c):
    d = preview(c)
    m = {**d["mandate_draft"], "mandate_id": "FAKE-00"}
    r = c.post("/mandate/sign", json={"mandate": m})
    assert r.status_code == 200 and r.json()["mandate_id"] != "FAKE-00"

def test_sign_rechecks_deadline_past(c):
    d = preview(c)
    m = d["mandate_draft"]
    m["execution_window"]["not_after"] = "2026-01-01"
    r = c.post("/mandate/sign", json={"mandate": m})
    assert r.status_code == 422 and human(r) == "deadline_past"

def test_sign_rechecks_gate_on_tampered_amount(c):
    d = preview(c)
    m = d["mandate_draft"]
    m["amount_range"]["max_price_t"] = 10**12
    r = c.post("/mandate/sign", json={"mandate": m})
    assert r.status_code == 422 and human(r) == "gate_blocked"

def test_sign_zero_qty_rejected_by_schema_with_russian_text(c):
    d = preview(c)
    m = d["mandate_draft"]
    m["line_items"][0]["qty_t"] = 0
    r = c.post("/mandate/sign", json={"mandate": m})
    assert r.status_code == 422
    assert "тонн" in r.text

def test_sign_empty_body_is_4xx(c):
    assert c.post("/mandate/sign", json={}).status_code == 422

def test_fifty_mandates_into_one_basket_concurrently(c):
    drafts = [preview(c, qty_t=10 + i)["mandate_draft"] for i in range(50)]
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        rs = list(ex.map(lambda m: c.post("/mandate/sign", json={"mandate": m}), drafts))
    assert all(r.status_code == 200 for r in rs)
    ids = [r.json()["mandate_id"] for r in rs]
    assert len(set(ids)) == 50
    bid = store.open_basket_id()
    summ = c.get(f"/book/basket/{bid}").json()
    assert summ["n_buyers"] == 50 and summ["demand_t"] == sum(10 + i for i in range(50))
    res = c.post(f"/clearing/run/{bid}").json()
    got = sum(a["qty_t"] for a in res["allocations"]) + sum(u["qty_t"] for u in res["unfilled"])
    assert got == summ["demand_t"]

def test_close_empty_basket_gives_no_price_not_500(c):
    bid = store.open_basket_id()
    r = c.post(f"/clearing/run/{bid}")
    assert r.status_code == 200
    d = r.json()
    assert d["clearing_price_t"] is None and d["allocations"] == [] and d["unfilled"] == []
    assert d["next_basket_id"] != bid

def test_close_basket_twice_returns_same_run(c):
    sign(c)
    bid = store.open_basket_id()
    r1 = c.post(f"/clearing/run/{bid}").json()
    r2 = c.post(f"/clearing/run/{bid}").json()
    assert r1["run_id"] == r2["run_id"] and r1["allocations"] == r2["allocations"]

def test_closed_basket_takes_no_new_mandates(c):
    bid = store.open_basket_id()
    c.post(f"/clearing/run/{bid}")
    s = sign(c)
    assert s["basket_id"] != bid
    assert s["mandate_id"] not in store.S.baskets[bid].mandate_ids
    r = c.post(f"/clearing/run/{bid}").json()
    assert all(a["mandate_id"] != s["mandate_id"] for a in r["allocations"])

def test_close_unknown_basket_is_404_russian(c):
    r = c.post("/clearing/run/B-gold-99-00000000-0000")
    assert r.status_code == 404 and CYR.search(human(r))

def test_mandate_expiring_before_basket_not_executed(c):
    s = sign(c, deadline="2026-11-08")
    bid = s["basket_id"]
    res = c.post(f"/clearing/run/{bid}").json()
    assert all(a["mandate_id"] != s["mandate_id"] for a in res["allocations"])

def test_basket_mode_unknown_is_4xx(c):
    bid = store.open_basket_id()
    assert c.get(f"/book/basket/{bid}?mode=admin").status_code == 422

def test_basket_admin_query_param_reveals_nothing(c):
    sign(c)
    bid = store.open_basket_id()
    d = c.get(f"/book/basket/{bid}?admin=1").json()
    assert "bids" not in d and "asks" not in d

def test_buyer_view_has_no_ceilings(c):
    sign(c, max_price_t=987_654)
    bid = store.open_basket_id()
    for mode in ("buyer", "plant", "supervisor"):
        assert "987654" not in c.get(f"/book/basket/{bid}?mode={mode}").text

def test_ladder_step_out_of_range_is_4xx(c):
    assert c.get("/book/ladder?step=0").status_code == 422
    assert c.get("/book/ladder?step=10000000").status_code == 422

def test_ladder_unknown_basket_is_404(c):
    assert c.get("/book/ladder?basket=NOPE").status_code == 404

@pytest.fixture()
def deals():
    out = scenario.reset(2)
    run = store.S.runs[out["run_id"]]
    filled = sorted({a.mandate_id for a in run.allocations})
    unfilled = sorted({u.mandate_id for u in run.unfilled})
    yield TestClient(app, raise_server_exceptions=False), run, filled, unfilled
    scenario.reset(1)

def _pay(cl, mid):
    r = cl.post(f"/escrow/{mid}/event", json={"type": "payment_confirmed"})
    assert r.status_code == 200, r.text

def test_ettn_for_foreign_deal_is_404(deals):
    cl, run, filled, _ = deals
    _pay(cl, filled[0])
    doc = {"doc": "ETTN", "deal_id": f"{run.run_id}:{filled[1]}", "qty_t": 1, "amount": 1, "signatures": 4}
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed", "ettn": doc})
    assert r.status_code == 404 and CYR.search(human(r))
    assert cl.get(f"/escrow/{filled[0]}").json()["state"] == "PAID_IN_FULL"

def test_ettn_signed_twice_is_ignored(deals):
    cl, _, filled, _ = deals
    _pay(cl, filled[0])
    r1 = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed"}).json()
    r2 = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed"}).json()
    assert r1["escrow"]["state"] == "RELEASED" and r2["ignored"] is True
    hist = cl.get(f"/escrow/{filled[0]}").json()["history"]
    assert sum(1 for h in hist if h["to"] == "RELEASED") == 1

def test_reject_after_release_is_409_russian(deals):
    cl, _, filled, _ = deals
    _pay(cl, filled[0])
    cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed"})
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_rejected", "reason": "нет"})
    assert r.status_code == 409 and CYR.search(human(r))

def test_ettn_before_payment_is_409(deals):
    cl, _, filled, _ = deals
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed"})
    assert r.status_code == 409

def test_ettn_three_signatures_is_422_without_move(deals):
    cl, _, filled, _ = deals
    _pay(cl, filled[0])
    doc = {"doc": "ETTN", "qty_t": 1, "amount": 1, "signatures": 3}
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed", "ettn": doc})
    assert r.status_code == 422 and "подпис" in human(r)
    assert cl.get(f"/escrow/{filled[0]}").json()["state"] == "PAID_IN_FULL"

def test_ettn_qty_off_by_06_percent_disputes(deals):
    cl, _, filled, _ = deals
    _pay(cl, filled[0])
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed", "qty_factor": 1.006}).json()
    assert r["escrow"]["state"] == "DISPUTED"

def test_ettn_garbage_fields_give_russian_text(deals):
    cl, _, filled, _ = deals
    _pay(cl, filled[0])
    doc = {"doc": "ETTN", "qty_t": "abc", "amount": 1, "signatures": "four"}
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed", "ettn": doc})
    assert r.status_code == 422 and CYR.search(human(r))

def test_ettn_garbage_fields_never_500(deals):
    cl, _, filled, _ = deals
    _pay(cl, filled[0])
    for doc in ({"qty_t": "abc", "signatures": 4}, {"signatures": "x"}, {"qty_t": None, "amount": None}):
        r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "ettn_signed", "ettn": {"doc": "ETTN", **doc}})
        assert r.status_code < 500, doc

def test_escrow_bad_time_never_500(deals):
    cl, _, filled, _ = deals
    r = cl.post(f"/escrow/{filled[0]}/event", json={"type": "timeout", "at": "вчера"})
    assert r.status_code == 422

def test_escrow_unknown_event_is_422(deals):
    cl, _, filled, _ = deals
    assert cl.post(f"/escrow/{filled[0]}/event", json={"type": "steal"}).status_code == 422

def test_unfilled_mandate_money_cannot_be_released(deals):
    cl, _, _, unfilled = deals
    mid = unfilled[0]
    for ev in ("cleared", "payment_confirmed", "ettn_signed"):
        cl.post(f"/escrow/{mid}/event", json={"type": ev})
    assert cl.get(f"/escrow/{mid}").json()["state"] != "RELEASED"

def test_unfilled_mandate_cannot_pay(deals):
    cl, _, _, unfilled = deals
    r = cl.post(f"/escrow/{unfilled[0]}/event", json={"type": "payment_confirmed"})
    assert r.status_code == 409

@pytest.mark.parametrize("path", [
    "/mandate/NOPE-00", "/escrow/NOPE", "/audit/NOPE", "/explain/NOPE", "/clearing/result/R-0000000000",
    "/book/basket/NOPE", "/plant/NOPE/demand",
])
def test_unknown_ids_are_404_with_russian_text(c, path):
    r = c.get(path)
    assert r.status_code == 404 and CYR.search(human(r)), r.text

def test_forged_run_id_with_real_mandate_is_404(deals):
    cl, _, filled, _ = deals
    for p in (f"/escrow/R-0000000000:{filled[0]}", f"/audit/R-0000000000:{filled[0]}"):
        r = cl.get(p)
        assert r.status_code == 404, p

def test_deal_id_garbage_never_500(deals):
    cl, _, _, _ = deals
    for did in (":::", "R-:", "%00", "a" * 500, "R-x:" + "y" * 300):
        for p in (f"/escrow/{did}", f"/audit/{did}", f"/explain/{did}"):
            assert cl.get(p).status_code < 500, p

def test_explain_unknown_lang_falls_back_to_ru(deals):
    cl, _, filled, _ = deals
    d = cl.get(f"/explain/{filled[0]}?lang=xx").json()
    assert d["lang"] == "ru"

def test_demo_step_out_of_range_is_422_russian(c):
    r = c.post("/demo/step/7")
    assert r.status_code == 422 and CYR.search(human(r))
