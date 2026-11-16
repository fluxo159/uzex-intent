from fastapi.testclient import TestClient

from app.audit import sources
from app.main import app
from app.radar import flags as fl
from app.radar import graph

def P(pid, region="Namangan", addr=None, role="buyer"):
    return {"id": pid, "inn": "8" + pid, "name": f"Участник {pid} (вымышленный)", "role": role, "region": region,
            "warehouse_address": addr or f"склад {pid}"}

def deal(i, buyer, seller, broker, region="Namangan"):
    return {"deal_no": f"D{i}", "buyer": buyer, "seller": seller, "broker": broker, "delivery_region": region}

def broker_data():
    deals, i = [], 0
    for buyer, total, via in (("A", 9, 8), ("B", 7, 6)):
        for k in range(total):
            i += 1
            deals.append(deal(i, buyer, f"S{k % 4}", "BK-07" if k < via else f"BK-{i}"))
    deals.append(deal(99, "C", "S0", "BK-01"))
    parts = [P("A"), P("B"), P("C")] + [P(f"S{k}", role="seller") for k in range(4)]
    return {"participants": parts, "deals": deals}

def test_shared_broker_edge_with_fact():
    G = graph.build(broker_data())
    e = [d for _, _, d in G.edges(data=True) if d["kind"] == "shared_broker"]
    assert len(e) == 1 and e[0]["fact"] == "оба через брокера BK-07 в 14 из 16 сделок"

def test_flag_two_bids_same_component():
    G = graph.build(broker_data())
    f = fl.flags(G, [{"mandate_id": "m1", "participant": "A"}, {"mandate_id": "m2", "participant": "B"},
                     {"mandate_id": "m3", "participant": "C"}])
    assert len(f) == 1 and f[0]["mandate_ids"] == ["m1", "m2"] and f[0]["scoring"] is None
    assert f[0]["edges"][0]["fact"].startswith("оба через брокера BK-07")
    assert "ЗПД ст. 24" in f[0]["appeal"]

def test_different_components_no_flag():
    G = graph.build(broker_data())
    assert fl.flags(G, [{"mandate_id": "m1", "participant": "A"}, {"mandate_id": "m3", "participant": "C"}]) == []

def test_empty_graph_no_flags_no_exceptions():
    G = graph.build({})
    assert fl.flags(G, []) == [] and fl.flags(G, [{"mandate_id": "x", "participant": "nobody"}]) == []

def test_frequent_pair_and_address_edges():
    deals = [deal(i, "A", "S", "BK-1") for i in range(5)] + [deal(9, "A", "T", "BK-2")]
    data = {"participants": [P("A", addr="ул. Вымышленная, 1"), P("B", addr="ул. Вымышленная, 1"),
                             P("S", role="seller"), P("T", role="seller")], "deals": deals}
    G = graph.build(data)
    kinds = sorted(d["kind"] for _, _, d in G.edges(data=True))
    assert kinds == ["frequent_pair", "shared_address"]

def test_pair_threshold_share():
    deals = [deal(i, "A", "S", "BK-1") for i in range(5)] + [deal(10 + i, "A", f"T{i}", "BK-1") for i in range(4)]
    G = graph.build({"participants": [P("A"), P("S", role="seller")] + [P(f"T{i}", role="seller") for i in range(4)],
                     "deals": deals})
    assert not any(d["kind"] == "frequent_pair" for _, _, d in G.edges(data=True))

def test_foreign_region_node_fact():
    deals = [deal(i, "A", "S", f"BK-{i}", region="Andijan") for i in range(3)]
    G = graph.build({"participants": [P("A", region="Namangan"), P("S", role="seller")], "deals": deals})
    assert G.nodes["A"]["node_facts"] == ["3 из 3 сделок с поставкой не в регион регистрации"]

def test_synthetic_file_fictional():
    d = graph.load_synthetic()
    assert len(d["participants"]) == 17 and all("вымышл" in p["name"].lower() for p in d["participants"])
    assert d["label"] == "ДЕМО: участники вымышленные"

def test_synthetic_baskets():
    d = graph.load_synthetic()
    r1 = fl.run_flags(d, "RADAR-DEMO-1")
    assert len(r1["flags"]) == 1 and r1["flags"][0]["mandate_ids"] == ["RM-1", "RM-2"]
    assert any("14 из 16" in e["fact"] for e in r1["flags"][0]["edges"])
    assert fl.run_flags(d, "RADAR-DEMO-2")["flags"][0]["edges"][0]["kind"] == "shared_address"
    assert fl.run_flags(d, "RADAR-DEMO-CLEAN")["flags"] == []
    assert fl.run_flags(d, "nope") is None

def test_endpoints():
    c = TestClient(app)
    j = c.get("/radar/flags/RADAR-DEMO-1").json()
    assert j["demo"] is True and len(j["flags"]) == 1
    assert c.get("/radar/flags/R-unknown").status_code == 404
    g = c.get("/radar/graph").json()
    assert len(g["nodes"]) == 17 and len(g["edges"]) >= 6

def test_endpoint_real_run_mapped_by_inn():
    sources.reset()
    basket = {"bids": [{"mandate_id": "x1", "qty_t": 5, "max_price_t": 1, "region": "Namangan"},
                       {"mandate_id": "x2", "qty_t": 5, "max_price_t": 1, "region": "Namangan"}], "asks": []}
    sources.register_run({"run_id": "R-real", "allocations": []}, basket)
    sources.register_mandate("x1", inn="800000004")
    sources.register_mandate("x2", inn="800000005")
    j = TestClient(app).get("/radar/flags/R-real").json()
    assert len(j["flags"]) == 1 and j["flags"][0]["mandate_ids"] == ["x1", "x2"]
    sources.reset()

def test_flag_on_core_scenario_run():
    import json
    from app import config
    scen = json.loads((config.DATA_DEMO / "scenario_2035.json").read_text(encoding="utf-8"))
    inns = {b["key"]: b["inn"] for b in scen["buyers"]}
    d = graph.load_synthetic()
    assert {inns["b1"], inns["b4"]} <= {p["inn"] for p in d["participants"]}
    c = TestClient(app)
    assert c.post("/demo/reset").status_code == 200
    assert c.post("/demo/step/2").status_code == 200
    rid = sources.runs()[-1]
    j = c.get(f"/radar/flags/{rid}").json()
    assert len(j["flags"]) == 1
    f = j["flags"][0]
    assert {p["inn"] for p in f["participants"]} == {inns["b1"], inns["b4"]}
    assert sorted(e["kind"] for e in f["edges"]) == ["shared_address", "shared_broker"]
    assert any(e["fact"] == "оба через брокера BK-21 в 14 из 16 сделок" for e in f["edges"])
    assert all("вымышл" in p["name"] for p in f["participants"]) and j["demo"] is True
    c.post("/demo/reset")
