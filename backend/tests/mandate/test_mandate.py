import datetime as dt
import json

import pytest
from pydantic import ValidationError

from app.mandate import canonical, fees, validator
from app.mandate.schema import LineItem, MandateFields, check_fields, compute_expiry

NOW = dt.datetime(2026, 11, 8, 10, 0)

def test_fees_200t_1m():
    f = fees.compute(200, 1_000_000)
    assert f["gross_max"] == 200_000_000
    assert f["exchange_fee"] == 403_200
    assert f["deposit_worst"] == 20_000_000
    assert f["total_worst"] == 200_403_200
    assert f["needed_now"] == 20_403_200
    assert f["deposit_final"] is False

def test_fee_rounding_half_up():
    assert fees.exchange_fee(333_333) == 672
    assert fees.round_half_up(0.5) == 1 and fees.round_half_up(1.5) == 2 and fees.round_half_up(2.5) == 3

def test_fees_calc_samples():
    samples = json.loads((fees.config.DATA_DEMO / "calc_samples.json").read_text(encoding="utf-8"))
    for s in samples["samples"]:
        assert abs(fees.exchange_fee(s["amount"]) - s["buyer_fee"]) <= 1

def test_fees_known_deposit_rate():
    f = fees.compute(10, 500_000, deposit_rate=0.05)
    assert f["deposit_worst"] == 250_000 and f["deposit_final"] is True

@pytest.mark.parametrize("q,p", [(0, 100), (-5, 100), (5, 0)])
def test_fees_reject_non_positive(q, p):
    with pytest.raises(ValueError):
        fees.compute(q, p)

def test_canonical_key_order_and_unicode_same_hash():
    a = {"b": 1, "a": {"y": "Наманган", "x": [1, 2]}, "d": dt.datetime(2026, 11, 8, 10, 0)}
    b = {"d": dt.datetime(2026, 11, 8, 10, 0), "a": {"x": [1, 2], "y": "Наманган"}, "b": 1}
    assert canonical.dumps(a) == canonical.dumps(b)
    assert canonical.sha256(a) == canonical.sha256(b)
    assert "Наманган" in canonical.dumps(a)
    assert '"2026-11-08T10:00:00Z"' in canonical.dumps(a)
    assert ", " not in canonical.dumps(a)

def test_canonical_one_digit_changes_hash():
    assert canonical.sha256({"q": 200}) != canonical.sha256({"q": 20})

def test_canonical_no_exponent():
    assert canonical.dumps({"x": 1e-7}) == '{"x":"0.0000001"}'
    assert canonical.dumps({"x": 2.0}) == '{"x":2}'

@pytest.mark.parametrize("q", [0, -5, 2.5, "2.5"])
def test_line_item_qty_rejected(q):
    with pytest.raises(ValidationError):
        LineItem(commodity="cement", qty_t=q)

def test_line_item_ok():
    assert LineItem(commodity="cement", qty_t=200).qty_t == 200

def test_price_out_of_corridor_is_warning_not_error():
    errs, warns = check_fields(MandateFields(commodity="cement", qty_t=10, max_price_t=150_000), NOW)
    assert not errs and warns[0].code == "price_far_from_market"

def test_deadline_in_past_is_error():
    errs, _ = check_fields(MandateFields(deadline=dt.date(2026, 11, 7)), NOW)
    assert errs[0].code == "deadline_past"

def test_expiry_min_of_deadline_and_14_days():
    assert compute_expiry(dt.date(2026, 11, 15), NOW) == dt.datetime(2026, 11, 15, 23, 59)
    assert compute_expiry(dt.date(2027, 1, 1), NOW) == NOW + dt.timedelta(days=14)

def test_validator_number_from_transcript_passes():
    t = "200 тонн цемента м400 наманган до 15 ноября не дороже 1 000 000"
    assert validator.check({"qty_t": 200, "max_price_t": 1_000_000, "grade": "32.5"}, t) == []

def test_validator_invented_number_rejected():
    t = "200 тонн цемента наманган не дороже 1000000"
    assert validator.check({"qty_t": 250, "max_price_t": 1_000_000}, t) == ["qty_t"]

def test_validator_computed_bags_pass():
    t = "40 мешков цемента в карши"
    assert validator.check({"qty_t": 2}, t, computed={"qty_t"}) == []
    assert validator.check({"qty_t": 2}, t) == ["qty_t"]

def test_principal_kinds_include_guest():
    from app.mandate.schema import Principal
    for k in ("ip", "company", "person_2035", "guest"):
        assert Principal(kind=k).kind == k
    with pytest.raises(ValidationError):
        Principal(kind="robot")
