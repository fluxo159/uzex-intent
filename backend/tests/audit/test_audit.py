import copy

import pytest
from fastapi.testclient import TestClient

from app.audit import decision_card as dc
from app.audit import sources
from app.clearing import engine
from app.clearing.models import Ask, Basket, Bid
from app.escrow import store
from app.main import app

def make():
    b = Basket(basket_id="B1", bids=[Bid(mandate_id="m1", qty_t=20, max_price_t=1_000_000, region="Namangan"),
                                     Bid(mandate_id="m2", qty_t=10, max_price_t=100_000, region="Namangan")],
               asks=[Ask(offer_id="o1", seller="Toshkent Conch Cement", qty_t=300, min_price_t=490_000,
                         warehouse_region="Tashkent_region")])
    return engine.run(b, {("Tashkent_region", "Namangan"): 41_000}), b

@pytest.fixture(autouse=True)
def clean():
    sources.reset()
    store.reset()
    yield
    sources.reset()
    store.reset()

def test_card_has_all_hashes():
    res, _ = make()
    c = dc.build(res, "m1", "a" * 64, {"receipt_id": "RC-1", "demo": True}, {"mandate_id": "m1", "sentences_ru": ["x"]})
    for k in ("mandate_hash", "inputs_hash", "engine_version", "tie_break_used", "clearing_price", "allocations",
              "explanation_hash", "signer_receipt", "approved_by", "appeal_channel", "card_hash"):
        assert c[k], k
    assert c["inputs_hash"] == res.inputs_hash and c["approved_by"] == "принципал (подпись поручения)"
    assert len(c["allocations"]) == 1 and c["allocations"][0]["mandate_id"] == "m1"
    assert dc.verify(c)

def test_allocation_change_changes_hash():
    res, _ = make()
    c1 = dc.build(res, "m1", "h")
    res2 = res.model_copy(deep=True)
    res2.allocations[0].qty_t += 1
    c2 = dc.build(res2, "m1", "h")
    assert c1["card_hash"] != c2["card_hash"]
    tampered = copy.deepcopy(c1)
    tampered["clearing_price"] = 1
    assert not dc.verify(tampered)

def test_explanation_change_changes_hash():
    res, _ = make()
    a = dc.build(res, "m1", "h", explanation={"mandate_id": "m1", "sentences_ru": ["один"]})
    b = dc.build(res, "m1", "h", explanation={"mandate_id": "m1", "sentences_ru": ["два"]})
    assert a["explanation_hash"] != b["explanation_hash"] and a["card_hash"] != b["card_hash"]

def test_unfilled_card_no_allocations():
    res, _ = make()
    c = dc.build(res, "m2", "h")
    assert c["allocations"] == [] and c["unfilled"][0]["reason"] == "price_below_clearing"

def test_endpoint():
    res, b = make()
    sources.register_run(res, b)
    sources.register_mandate("m1", hash="f" * 64, receipt={"receipt_id": "RC-1", "demo": True})
    c = TestClient(app)
    j = c.get(f"/audit/{res.run_id}:m1").json()
    assert j["mandate_hash"] == "f" * 64 and j["explanation_hash"] and j["escrow_state"] == "MATCHED"
    assert c.get("/audit/m1").json()["deal_id"] == f"{res.run_id}:m1"
    assert c.get("/audit/R-x:m1").status_code == 404
    assert c.get(f"/audit/{res.run_id}:nobody").status_code == 404
    assert c.get("/audit/nobody").status_code == 404
