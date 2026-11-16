import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.main import app

SNAP = pathlib.Path(__file__).parent / "snapshots" / "clearing_2035.json"

def collect() -> dict:
    out: dict = {}
    with TestClient(app) as c:
        assert c.post("/demo/step/0").status_code == 200
        sc = c.get("/demo/scenario").json()
        from app.demo.scenario import scenario
        raw = {b["key"]: b for b in scenario()["buyers"]}
        ids = {}
        out["mandates"] = {}
        for b in sc["buyers"]:
            parsed = c.post("/intake/parse", json={"text": b["phrase"], "lang": b["lang"]}).json()
            fields = parsed["fields"]
            exp = scenario()["expected_fields"][b["key"]]
            assert {k: fields.get(k) for k in exp} == exp, b["key"]
            rb = raw[b["key"]]
            body = {"fields": fields, "principal": {"kind": rb["kind"], "inn": rb.get("inn"), "region": rb["region"]},
                    "transcript_norm": parsed.get("transcript_norm", ""), "lang": b["lang"],
                    "funds_available": rb.get("funds_available")}
            pv = c.post("/mandate/preview", json=body).json()
            assert pv["mandate_draft"], (b["key"], pv["errors"])
            draft = dict(pv["mandate_draft"], created_at=rb["created_at"],
                         execution_window=dict(pv["mandate_draft"]["execution_window"], not_before=rb["created_at"]))
            sg = c.post("/mandate/sign", json={"mandate": draft, "funds_available": rb.get("funds_available")}).json()
            ids[b["key"]] = sg["mandate_id"]
            out["mandates"][b["key"]] = {"fees": {k: pv["fees"][k] for k in ("gross_max", "exchange_fee", "deposit_worst")},
                                         "gate": pv["gate"]["status"], "hash": sg["hash"]}
        r = c.post("/clearing/run/open").json()
        key_of = {v: k for k, v in ids.items()}
        out["clearing"] = {
            "price": r["clearing_price_t"], "tie_break": r["tie_break_used"], "executed_t": r["executed_qty_t"],
            "allocations": sorted([[key_of[a["mandate_id"]], a["seller"], a["qty_t"], a["delivered_price_t"]]
                                   for a in r["allocations"]]),
            "unfilled": sorted([[key_of[u["mandate_id"]], u["qty_t"], u["reason"], u["fill_at_max_price_t"]]
                                for u in r["unfilled"]]),
            "lots": sorted([[g["seller"], g["qty_t"], g["n_mandates"]] for g in r["lot_groups"]]),
        }
        out["explain"] = {}
        for k, mid in sorted(ids.items()):
            e = {lang: c.get(f"/explain/{mid}", params={"lang": lang}).json() for lang in ("ru", "uz")}
            out["explain"][k] = {"outcome": e["ru"]["outcome"], "ru": e["ru"]["sentences_ru"], "uz": e["uz"]["sentences_uz"]}
        run_id = r["run_id"]
        states = {}
        for k, events in (("b1", ["payment_confirmed", "ettn_signed"]), ("b2", ["payment_confirmed", "ettn_rejected"])):
            did = f"{run_id}:{ids[k]}"
            for ev in events:
                body = {"type": ev}
                if ev == "ettn_rejected":
                    body["reason"] = "груз не соответствует"
                resp = c.post(f"/escrow/{did}/event", json=body)
                assert resp.status_code == 200, resp.text
            states[k] = c.get(f"/escrow/{did}").json()["escrow"]["state"] if "escrow" in c.get(f"/escrow/{did}").json() \
                else c.get(f"/escrow/{did}").json()["state"]
        out["escrow"] = states
        cf = c.get("/market/counterfactual/ai92").json()
        out["ai92"] = {k: cf[k] for k in cf if isinstance(cf[k], (int, str)) and k not in ("source", "note")}
        pd = c.get("/plant/Toshkent Conch Cement/demand").json()
        out["plant_tcc"] = {"price_t": pd["price_t"], "left_t": pd["qty_t"], "last_run": pd["last_run"]["lot_groups"]}
        c.post("/demo/reset")
    return out

def test_golden_scenario(request):
    got = json.loads(json.dumps(collect(), ensure_ascii=False))
    if request.config.getoption("--update-snapshots") or not SNAP.exists():
        SNAP.parent.mkdir(exist_ok=True)
        SNAP.write_text(json.dumps(got, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        if not request.config.getoption("--update-snapshots"):
            pytest.skip("снимок создан впервые — перезапустите")
    want = json.loads(SNAP.read_text(encoding="utf-8"))
    assert got == want

def test_golden_core_numbers():
    got = collect()["clearing"]
    assert got["price"] == 490_000 and got["executed_t"] == 325
    assert [u[0] for u in got["unfilled"]] == ["b3", "b7"]
