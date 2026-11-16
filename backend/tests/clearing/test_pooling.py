from app.clearing.engine import run
from .helpers import ask, bid, book

def test_seven_small_orders_form_one_lot():
    qs = [5, 5, 10, 10, 10, 15, 20]
    r = run(book([bid(f"b{i}", q, 1000, minute=i) for i, q in enumerate(qs)], [ask("A", 100, 500, lot=50)]))
    assert r.executed_qty_t == 75
    assert len(r.lot_groups) == 1 and r.lot_groups[0].n_mandates == 7 and r.lot_groups[0].qty_t == 75

def test_small_group_moved_to_second_plant():
    tar = {("R1", "R2"): 50}
    r = run(book([bid(f"b{i}", 10, 1000, region="R1", minute=i) for i in range(3)],
                 [ask("A", 100, 100, region="R1", lot=50), ask("B", 100, 100, region="R2", lot=10)]), tar)
    assert r.executed_qty_t == 30
    assert {a.offer_id for a in r.allocations} == {"B"}
    assert all(a.delivered_price_t == 150 for a in r.allocations)
    assert not r.unfilled

def test_lot_not_formed_orders_stay():
    r = run(book([bid(f"b{i}", 10, 1000, minute=i) for i in range(3)], [ask("A", 100, 100, lot=50)]))
    assert r.executed_qty_t == 0
    assert {u.reason for u in r.unfilled} == {"lot_not_formed"}
    assert sum(u.qty_t for u in r.unfilled) == 30
    assert r.asks_unfilled[0].reason == "lot_not_formed"

def test_min_lot_bigger_than_all_demand():
    r = run(book([bid("b", 40, 1000)], [ask("A", 500, 100, lot=55)]))
    assert r.executed_qty_t == 0 and r.unfilled[0].reason == "lot_not_formed"

def test_exact_lot_is_formed():
    r = run(book([bid("b1", 30, 1000), bid("b2", 20, 1000, minute=1)], [ask("A", 100, 100, lot=50)]))
    assert r.executed_qty_t == 50
