from fastapi.testclient import TestClient

from app.gate import eligibility as el
from app.gate import funds, registry
from app.main import app

IP = {"kind": "ip", "inn": "900000001", "region": "Namangan"}
CEMENT = [{"commodity": "cement", "qty_t": 20, "max_price_t": 600_000}]
NEED = 1_224_192

def by(res, name):
    return [c for c in res["checks"] if c["name"] == name]

def test_ip_active_enough_money_ok():
    r = el.check(IP, CEMENT, 30_000_000)
    assert r["status"] == "ok" and all(c["passed"] for c in r["checks"])
    assert by(r, "funds")[0]["required"] == NEED

def test_company_not_found_blocked():
    r = el.check({"kind": "company", "inn": "123456789"}, CEMENT, 10**9)
    c = by(r, "company_status")[0]
    assert r["status"] == "blocked" and c["how_to_fix"] == "проверьте ИНН"

def test_suspended_blocked():
    r = el.check({"kind": "company", "inn": "900000008"}, CEMENT, 10**9)
    assert r["status"] == "blocked" and "приостановлена" in by(r, "company_status")[0]["reason"]

def test_cotton_without_recommendation_blocked():
    r = el.check({"kind": "company", "inn": "900000006"}, [{"commodity": "хлопок", "qty_t": 10, "max_price_t": 1000}], 10**9)
    c = by(r, "commodity_right")[0]
    assert r["status"] == "blocked" and c["how_to_fix"] == "получить рекомендацию хокимията"
    r = el.check({"kind": "company", "inn": "900000005"}, [{"commodity": "cotton", "qty_t": 10, "max_price_t": 1000}], 10**9)
    assert r["status"] == "ok"

def test_lpg_without_license_blocked():
    r = el.check(IP, [{"commodity": "СУГ", "qty_t": 5, "max_price_t": 1000}], 10**9)
    assert r["status"] == "blocked" and "Лицензия" in by(r, "commodity_right")[0]["how_to_fix"]
    r = el.check({"kind": "company", "inn": "900000007"}, [{"commodity": "lpg", "qty_t": 5, "max_price_t": 1000}], 10**9)
    assert r["status"] == "ok"

def test_person_2035_warning_not_block():
    r = el.check({"kind": "person_2035", "region": "Namangan"}, CEMENT, 30_000_000)
    c = by(r, "principal_kind")[0]
    assert r["status"] == "warning" and c["passed"] and "п. 4" in c["reason"] and "2019" in c["reason"]

def test_balance_exactly_equal_ok():
    r = el.check(IP, CEMENT, NEED)
    assert r["status"] == "ok" and by(r, "funds")[0]["shortfall"] == 0

def test_balance_minus_one_blocked_exact_shortfall():
    r = el.check(IP, CEMENT, NEED - 1)
    f = by(r, "funds")[0]
    assert r["status"] == "blocked" and f["shortfall"] == 1 and f["reason"] == "не хватает 1 сум; пополните счёт в РКП"

def test_zero_balance_blocked():
    r = el.check({"kind": "ip", "inn": "900000009"}, CEMENT)
    assert by(r, "funds")[0]["shortfall"] == NEED and r["status"] == "blocked"

def test_balance_from_registry_when_not_given():
    assert el.check(IP, CEMENT)["status"] == "ok"

def test_registry_down_warning_not_block():
    r = el.check(IP, CEMENT, 30_000_000, registry_down=True)
    assert r["status"] == "warning" and "повторим перед торгами" in by(r, "company_status")[0]["reason"]

def test_region_rule_warning():
    items = [dict(CEMENT[0], allowed_regions=["Qashqadaryo"])]
    r = el.check(IP, items, 30_000_000)
    assert r["status"] == "warning" and "п. 105" in by(r, "region_rule")[0]["reason"]
    r = el.check(IP, [dict(CEMENT[0], allowed_regions=["Namangan"])], 30_000_000)
    assert r["status"] == "ok"

def test_unknown_kind_and_commodity():
    assert el.check({"kind": "alien"}, CEMENT, 10**9)["status"] == "blocked"
    assert el.check(IP, [{"commodity": "уран", "qty_t": 1, "max_price_t": 1}], 10**9)["status"] == "blocked"

def test_funds_multiple_items_sum():
    r = funds.required([{"qty_t": 20, "max_price_t": 600_000}, {"qty_t": 1, "max_price_t": 333_333}])
    assert r["deposit_worst"] == 1_200_000 + 33_333 and r["exchange_fee"] == 24_192 + 672

def test_registry_fictional():
    ents = registry.entities()
    assert len(ents) == 12 and {"900000011", "900000012"} <= {e["inn"] for e in ents} and all("вымышл" in e["name"] for e in ents)
    assert {e["status"] for e in ents} == {"active", "suspended"}
    assert registry.mask_inn("900000001") == "******001"

def test_endpoint():
    c = TestClient(app)
    j = c.post("/gate/check", json={"principal": IP, "line_items": CEMENT, "funds_available": NEED - 1}).json()
    assert j["status"] == "blocked" and j["demo"] is True
    assert c.post("/gate/check", json={"principal": IP, "line_items": [{"qty_t": 2.5, "max_price_t": 1}]}).status_code == 422
    assert len(c.get("/gate/registry").json()["entities"]) == 12

def test_person_2035_demo_balance_when_not_given():
    r = el.check({"kind": "person_2035", "region": "Namangan"}, CEMENT)
    assert r["status"] == "warning" and by(r, "funds")[0]["funds_available"] == el.PERSON_DEMO_BALANCE

def test_guest_warning_demo_balance_no_inn():
    r = el.check({"kind": "guest", "principal_id": "guest-7"}, CEMENT)
    c = by(r, "principal_kind")[0]
    assert r["status"] == "warning" and c["passed"] and c["guest"] and "ДЕМО-участник" in c["reason"]
    assert by(r, "company_status")[0]["level"] == "ok"
    assert by(r, "funds")[0]["funds_available"] == el.PERSON_DEMO_BALANCE

def test_guest_over_demo_balance_blocked():
    big = [{"commodity": "cement", "qty_t": 500, "max_price_t": 1_000_000}]
    assert el.check({"kind": "guest"}, big)["status"] == "blocked"
    assert el.check({"kind": "guest"}, big, 10 ** 9)["status"] == "warning"

def test_guest_cannot_buy_restricted_goods():
    assert el.check({"kind": "guest"}, [{"commodity": "lpg", "qty_t": 1, "max_price_t": 1}])["status"] == "blocked"

def test_guest_signs_and_sees_own_mandate():
    from app.book import views
    from app.demo import scenario
    from app.mandate import service
    from app.mandate.schema import MandateFields, Principal
    scenario.reset(1)
    p = Principal(kind="guest", principal_id="guest-7")
    pv = service.preview(MandateFields(commodity="cement", grade="32.5", qty_t=20, region="Qashqadaryo",
                                       deadline="2026-11-15", max_price_t=650_000), p, "", "ru")
    assert pv.gate["status"] == "warning" and pv.mandate_draft is not None
    service.sign(pv.mandate_draft)
    assert [m["status"] for m in views.mine("guest-7")] == ["in_basket"]
    scenario.reset(1)
