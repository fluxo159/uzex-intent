from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.demo import scenario
from app.main import app

PHRASE = "200 тонн цемента М400 в Наманган до 15 ноября, не дороже 1 000 000 за тонну"

@pytest.fixture()
def ac():
    scenario.reset(1)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                             base_url="http://t")

def test_invalid_json_is_422_not_500(ac):
    async def go():
        async with ac:
            return await ac.post("/intake/parse", content=b"{not json", headers={"content-type": "application/json"})
    r = asyncio.run(go())
    assert r.status_code == 422

def test_wrong_content_type_is_4xx(ac):
    async def go():
        async with ac:
            return await ac.post("/mandate/preview", content=b"qty=200", headers={"content-type": "text/plain"})
    assert 400 <= asyncio.run(go()).status_code < 500

def test_unknown_route_is_404_and_wrong_method_405(ac):
    async def go():
        async with ac:
            return await ac.get("/no/such/route"), await ac.get("/clearing/run/open")
    a, b = asyncio.run(go())
    assert a.status_code == 404 and b.status_code == 405

def test_unknown_route_text_is_russian(ac):
    async def go():
        async with ac:
            return await ac.get("/no/such/route")
    import re
    assert re.search(r"[а-яё]", asyncio.run(go()).text, re.I)

def test_fifty_parallel_parses_all_answer_same(ac):
    async def go():
        async with ac:
            t0 = time.perf_counter()
            rs = await asyncio.gather(*[ac.post("/intake/parse", json={"text": PHRASE}) for _ in range(50)])
            return rs, time.perf_counter() - t0
    rs, took = asyncio.run(go())
    assert [r.status_code for r in rs] == [200] * 50
    fields = {tuple(sorted(r.json()["fields"].items())) for r in rs}
    assert len(fields) == 1
    f = rs[0].json()["fields"]
    assert (f["qty_t"], f["region"], f["max_price_t"]) == (200, "Namangan", 1_000_000)
    assert took < 30

def test_fifty_parallel_mixed_garbage_never_500(ac):
    bodies = [{"text": PHRASE}, {"text": ""}, {"text": "🙂" * 100}, {"text": "x" * 5000}, {"text": None},
              {"lang": "zz"}, {"text": 123}]

    async def go():
        async with ac:
            return await asyncio.gather(*[ac.post("/intake/parse", json=bodies[i % len(bodies)]) for i in range(50)])
    rs = asyncio.run(go())
    assert all(r.status_code < 500 for r in rs)
