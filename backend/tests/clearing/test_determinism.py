import random

from app.clearing.engine import run
from .helpers import ask, bid, book

def _book(seed=2035):
    rnd = random.Random(seed)
    bids = [bid(f"b{i}", rnd.randint(1, 50), rnd.randint(100, 200), minute=rnd.randint(0, 3)) for i in range(15)]
    asks = [ask(f"a{i}", rnd.randint(1, 50), rnd.randint(100, 200), minute=rnd.randint(0, 3)) for i in range(8)]
    return bids, asks

def test_ten_runs_same_result():
    bids, asks = _book()
    outs = {run(book(bids, asks)).model_dump_json() for _ in range(10)}
    assert len(outs) == 1

def test_permutation_same_result_and_hash():
    bids, asks = _book()
    base = run(book(bids, asks))
    rnd = random.Random(7)
    for _ in range(5):
        b2, a2 = bids[:], asks[:]
        rnd.shuffle(b2)
        rnd.shuffle(a2)
        assert run(book(b2, a2)).model_dump() == base.model_dump()

def test_input_change_changes_hash():
    bids, asks = _book()
    h1 = run(book(bids, asks)).inputs_hash
    bids[0] = bid("b0", bids[0].qty_t + 1, bids[0].max_price_t)
    assert run(book(bids, asks)).inputs_hash != h1
