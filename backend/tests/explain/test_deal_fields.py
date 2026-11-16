from fastapi.testclient import TestClient

from app.explain.service import deal_fields
from app.main import app

def test_deal_fields_filled_unfilled_and_split():
    res = {"run_id": "R-1", "allocations": [
        {"mandate_id": "m1", "seller": "A", "qty_t": 50, "tariff_t": 11_000, "delivered_price_t": 511_000},
        {"mandate_id": "m1", "seller": "B", "qty_t": 150, "tariff_t": 22_000, "delivered_price_t": 522_000},
        {"mandate_id": "m2", "seller": "B", "qty_t": 10, "tariff_t": 0, "delivered_price_t": 500_000}]}
    d = deal_fields(res, "m1")
    assert d["seller"] == "A + B" and d["delivery_t"] == 22_000 and d["deal_id"] == "R-1:m1" and len(d["parts"]) == 2
    assert deal_fields(res, "m2")["delivery_t"] == 0
    assert deal_fields(res, "zzz") == {"seller": None, "delivery_t": None, "deal_id": None, "parts": []}

def test_explain_endpoint_has_deal_fields():
    with TestClient(app) as c:
        r = c.post("/demo/step/2").json()
        from app.book import store
        b1 = next(mid for mid, m in store.S.mandates.items() if m.principal.inn == "900000001")
        e = c.get(f"/explain/{b1}").json()
        assert e["seller"] == "Toshkent Conch Cement" and e["delivery_t"] == 22_000
        assert e["deal_id"] == f"{r['run_id']}:{b1}"
        b3 = next(mid for mid, m in store.S.mandates.items() if m.principal.inn == "900000002")
        assert c.get(f"/explain/{b3}").json()["deal_id"] is None
        c.post("/demo/reset")
