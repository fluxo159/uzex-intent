from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import argparse
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DEMO_CLOCK", "fixed")

SLOW_MS = 300
timings: list[tuple[str, float, int]] = []
problems: list[str] = []

def fmt(n) -> str:
    return "—" if n is None else f"{int(n):,}".replace(",", " ")

class Client:
    def __init__(self, url: str | None):
        if url:
            import httpx
            self.c = httpx.Client(base_url=url, timeout=30)
            self.ctx = None
        else:
            from fastapi.testclient import TestClient
            from app.main import app
            self.ctx = TestClient(app)
            self.c = self.ctx.__enter__()

    def call(self, method: str, path: str, label: str | None = None, **kw):
        t = time.perf_counter()
        r = self.c.request(method, path, **kw)
        ms = (time.perf_counter() - t) * 1000
        timings.append((label or f"{method} {path}", ms, r.status_code))
        if r.status_code >= 400:
            problems.append(f"{method} {path} → {r.status_code}: {r.text[:200]}")
            return {}
        return r.json()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    args = ap.parse_args()
    c = Client(args.url)

    print("=== Сброс демо (сид 2035), только заводы ===")
    c.call("POST", "/demo/step/0", "POST /demo/step/0")
    from app.demo.scenario import scenario
    sc = scenario()
    for a in sc["asks"]:
        print(f"  завод {a['seller']:32s} склад {a['warehouse_region']:16s} {fmt(a['min_price_t'])} сум/т  "
              f"{a['qty_t']} т (демо-объём)  лот {a['min_lot_t']} т")

    print("\n=== 7 поручений: фраза → поля → сбор, задаток, допуск → подпись ===")
    ids: dict[str, str] = {}
    for b in sc["buyers"]:
        p = c.call("POST", "/intake/parse", "POST /intake/parse", json={"text": b["phrase"], "lang": b["lang"]})
        f = p.get("fields", {})
        exp = sc["expected_fields"][b["key"]]
        same = all(f.get(k) == v for k, v in exp.items())
        if not same:
            problems.append(f"{b['key']}: разбор не совпал с ожидаемым: {f} vs {exp}")
        body = {"fields": f, "principal": {"kind": b["kind"], "inn": b.get("inn"), "region": b["region"]},
                "transcript_norm": p.get("transcript_norm", ""), "lang": b["lang"], "funds_available": b.get("funds_available")}
        pv = c.call("POST", "/mandate/preview", "POST /mandate/preview", json=body)
        fe = pv.get("fees", {})
        print(f"  {b['key']} [{b['lang']}] «{b['phrase']}»")
        print(f"      поля: {f.get('qty_t')} т · {f.get('region')} · до {f.get('deadline')} · потолок {fmt(f.get('max_price_t'))}"
              f" · источник {p.get('source')} · {'совпало' if same else 'НЕ СОВПАЛО'}")
        print(f"      максимум {fmt(fe.get('gross_max'))} · сбор {fmt(fe.get('exchange_fee'))} · задаток ≤ {fmt(fe.get('deposit_worst'))}"
              f" · доставка {fmt(fe.get('delivery_min_t'))}–{fmt(fe.get('delivery_max_t'))} · допуск {pv.get('gate', {}).get('status')}")
        if not pv.get("mandate_draft"):
            problems.append(f"{b['key']}: карточка с ошибками {pv.get('errors')}")
            continue
        sg = c.call("POST", "/mandate/sign", "POST /mandate/sign",
                    json={"mandate": pv["mandate_draft"], "funds_available": b.get("funds_available")})
        ids[b["key"]] = sg.get("mandate_id")
        print(f"      подписано № {sg.get('mandate_id')} · квитанция {sg.get('receipt', {}).get('receipt_id')} (ДЕМО)")
    us = pv.get("usual_range", {})
    print(f"  «обычно от … до …» (90 дней, 32,5): {fmt(us.get('lo'))} … {fmt(us.get('hi'))}")

    bk = c.call("GET", "/book/basket/open")
    print(f"\n=== Корзина {bk.get('basket_id')} ({bk.get('date')} {bk.get('window')}) ===")
    print(f"  {bk.get('n_buyers')} покупателей на {bk.get('demand_t')} т, {bk.get('n_plants')} заводов на {bk.get('supply_t')} т")

    r = c.call("POST", "/clearing/run/open", "POST /clearing/run")
    key = {v: k for k, v in ids.items()}
    print(f"\n=== Клиринг {r.get('run_id')}: единая цена {fmt(r.get('clearing_price_t'))} сум/т на складе, "
          f"правило {r.get('tie_break_used')}, исполнено {r.get('executed_qty_t')} т ===")
    for a in r.get("allocations", []):
        print(f"  ● {key.get(a['mandate_id'], a['mandate_id'])} {a['qty_t']:>4} т  {a['seller']:30s} "
              f"{fmt(a['price_t'])} + доставка {fmt(a['tariff_t'])} = {fmt(a['delivered_price_t'])}")
    for u in r.get("unfilled", []):
        print(f"  ○ {key.get(u['mandate_id'], u['mandate_id'])} {u['qty_t']:>4} т  не исполнено: {u['reason']}"
              f" (вошло бы при потолке {fmt(u.get('fill_at_max_price_t'))})")
    for g in r.get("lot_groups", []):
        print(f"  лот {g['seller']}: {g['qty_t']} т из {g['n_mandates']} поручений {g['regions']}")
    if r.get("clearing_price_t") != 490_000:
        problems.append(f"цена корзины {r.get('clearing_price_t')} ≠ 490 000 из снимка")

    print("\n=== Объяснения (RU) ===")
    for k, mid in sorted(ids.items()):
        e = c.call("GET", f"/explain/{mid}", "GET /explain/{id}", params={"lang": "ru"})
        print(f"  {k} [{e.get('outcome')}]")
        for s in e.get("sentences_ru", []):
            print(f"      {s}")

    print("\n=== Деньги (ДЕМО) ===")
    for k, evs in (("b1", ["payment_confirmed", "ettn_signed"]), ("b2", ["payment_confirmed", "ettn_rejected"])):
        did = f"{r.get('run_id')}:{ids.get(k)}"
        chain = [c.call("GET", f"/escrow/{did}", "GET /escrow/{id}").get("escrow", {}).get("state")]
        for ev in evs:
            body = {"type": ev, **({"reason": "груз не соответствует"} if ev == "ettn_rejected" else {})}
            res = c.call("POST", f"/escrow/{did}/event", "POST /escrow/{id}/event", json=body)
            chain.append(res.get("escrow", {}).get("state"))
        print(f"  {k}: " + " → ".join(str(x) for x in chain))

    rf = c.call("GET", f"/radar/flags/{r.get('run_id')}", "GET /radar/flags/{run_id}")
    flags = rf.get("flags", [])
    print(f"\n=== Радар (ДЕМО, участники вымышленные): {len(flags)} флаг(ов) ===")
    for fl in flags:
        print(f"  {fl.get('summary')}: " + "; ".join(e.get("fact", "") for e in fl.get("edges", [])))
    if len(flags) != 1:
        problems.append(f"радар: ожидали 1 флаг на сценарии, получили {len(flags)}")

    cf = c.call("GET", "/market/counterfactual/ai92")
    print(f"\n=== АИ-92, 06.11.2026 ({cf.get('source', 'реестр UZEX')}) ===")
    prices = [d.get("price_t") for d in cf.get("deals", [])] if cf.get("deals") else []
    print(f"  5 цен: {' / '.join(fmt(p) for p in prices)}")
    print(f"  одна цена: {fmt(cf.get('uniform_price_t'))} · переплата, которой нет: {fmt(cf.get('overpay'))} сум · {cf.get('volumes_note')}")

    cal = c.call("GET", "/market/calendar")
    print("\n=== Календарь: 5 окон ===")
    for w in cal.get("windows", [])[:5]:
        print(f"  {w.get('label')}  {'(подтвердить)' if w.get('to_confirm') else ''}")

    ch = c.call("GET", "/market/chart", params={"grade": "32.5"})
    pts = ch.get("points", [])
    gaps = sum(1 for p in pts if p.get("vwap") is None)
    print(f"\n=== График 32,5: {len(pts)} точек, {gaps} разрывов, {pts[0]['date'] if pts else '—'} … {pts[-1]['date'] if pts else '—'} ===")

    pd = c.call("GET", "/plant/Toshkent Conch Cement/demand", "GET /plant/{seller}/demand")
    lr = (pd.get("last_run") or {})
    print(f"\n=== Завод Toshkent Conch: цена {fmt(pd.get('price_t'))}, продано {lr.get('sold_t')} т, осталось {pd.get('qty_t')} т ===")

    c.call("GET", "/book/tape")
    c.call("POST", "/demo/reset")

    print("\n=== Время ответа ===")
    agg: dict[str, list[float]] = {}
    for label, ms, code in timings:
        agg.setdefault(label, []).append(ms)
    for label, v in agg.items():
        worst = max(v)
        flag = "  МЕДЛЕННО" if worst > SLOW_MS and "intake" not in label else ""
        print(f"  {label:34s} {worst:7.1f} мс (×{len(v)}){flag}")
        if flag:
            problems.append(f"{label} {worst:.0f} мс > {SLOW_MS}")

    print("\n" + ("ЗЕЛЁНЫЙ" if not problems else "ПРОБЛЕМЫ:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
