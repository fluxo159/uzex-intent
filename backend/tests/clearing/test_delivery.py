from app.clearing.delivery import demo_tariff, tariff_t
from app.clearing.engine import run
from app.regions import REGIONS
from .helpers import ask, bid, book, got

TAR = {("R1", "R2"): 100}

def test_diagonal_zero_and_symmetric():
    assert tariff_t(TAR, "R1", "R1") == 0
    assert tariff_t(TAR, "R2", "R1") == 100
    assert tariff_t(TAR, "R1", "R3") is None
    assert tariff_t(None, "X", "X") == 0

def test_demo_tariff_covers_all_pairs_and_same_region_is_free():
    t = demo_tariff()
    for a in REGIONS:
        assert tariff_t(t, a, a) == 0
        for b in REGIONS:
            assert tariff_t(t, a, b) is not None

def test_tashkent_city_and_region_are_different_regions():
    assert tariff_t(demo_tariff(), "Tashkent_region", "Tashkent_city") > 0

def test_nearest_plant_chosen_first():
    r = run(book([bid("b", 15, 600, region="R1")],
                 [ask("A", 10, 450, region="R1"), ask("B", 10, 440, region="R2")]), TAR)
    assert r.clearing_price_t == 450
    by = {a.offer_id: a for a in r.allocations}
    assert by["A"].qty_t == 10 and by["A"].delivered_price_t == 450
    assert by["B"].qty_t == 5 and by["B"].delivered_price_t == 550

def test_ceiling_minus_tariff_below_price_unfilled():
    r = run(book([bid("b", 10, 500, region="R1")], [ask("B", 10, 450, region="R2")]), TAR)
    assert r.clearing_price_t is None
    assert r.unfilled[0].reason == "price_below_clearing"
    assert r.unfilled[0].fill_at_max_price_t == 550

def test_ceiling_minus_tariff_negative():
    r = run(book([bid("b", 10, 50, region="R1")], [ask("B", 10, 450, region="R2")]), TAR)
    assert r.executed_qty_t == 0 and r.unfilled[0].reason == "price_below_clearing"

def test_unreachable_plant_no_tariff():
    r = run(book([bid("b", 10, 900, region="R9")], [ask("B", 10, 450, region="R2")]), TAR)
    assert r.executed_qty_t == 0
    assert r.unfilled[0].fill_at_max_price_t is None

def test_buyer_never_pays_above_ceiling_with_delivery():
    r = run(book([bid("near", 10, 520, region="R1"), bid("far", 10, 520, region="R2")],
                 [ask("A", 20, 500, region="R1")]), TAR)
    assert got(r, "near") == 10 and got(r, "far") == 0
    hint = [u for u in r.unfilled if u.mandate_id == "far"][0]
    assert hint.fill_at_max_price_t == 600

def test_routing_minimizes_delivery_same_volumes():
    tar = {("Andijan", "Namangan"): 11, ("Tash", "Namangan"): 22, ("Tash", "Andijan"): 33}
    r = run(book([bid("nam", 50, 1000, region="Namangan", minute=0), bid("and", 50, 600, region="Andijan", minute=1)],
                 [ask("SBF", 50, 500, region="Andijan"), ask("TCC", 300, 500, region="Tash")]), tar)
    by = {(a.mandate_id, a.offer_id): a.qty_t for a in r.allocations}
    assert by == {("nam", "TCC"): 50, ("and", "SBF"): 50}
    assert got(r, "nam") == 50 and got(r, "and") == 50
