from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import Counter, defaultdict

import httpx

GETS = ["/book/basket/open", "/book/ladder", "/book/tape?n=5", "/clearing/history", "/market/chart?grade=32.5",
        "/market/calendar", "/market/counterfactual/ai92", "/plant", "/health"]
PHRASES = ["200 тонн цемента М400 в Наманган до 15 ноября не дороже 1 000 000",
           "Namanganga 200 tonna sement M400 15 noyabrgacha 1 000 000 dan qimmat emas",
           "нужно 60 тонн цемента в Джизак, максимум 950 тысяч",
           "120 т цемента 42,5 Ташкент до пятницы"]

class Stats:
    def __init__(self) -> None:
        self.lat: dict[str, list[float]] = defaultdict(list)
        self.codes: dict[str, Counter] = defaultdict(Counter)
        self.errors: Counter = Counter()

    def add(self, phase: str, status: int, ms: float) -> None:
        self.codes[phase][status] += 1
        self.lat[phase + (":ok" if status < 400 else ":other")].append(ms)

async def _req(c: httpx.AsyncClient, st: Stats, phase: str, method: str, path: str, **kw) -> None:
    t0 = time.perf_counter()
    try:
        r = await c.request(method, path, **kw)
        st.add(phase, r.status_code, (time.perf_counter() - t0) * 1000)
    except httpx.HTTPError as e:
        st.errors[f"{phase}:{type(e).__name__}"] += 1

async def hall_client(base: str, ip: str, until: float, think: float, st: Stats) -> None:
    async with httpx.AsyncClient(base_url=base, headers={"X-Real-IP": ip}, timeout=10) as c:
        await _req(c, st, "зал", "GET", "/auth/me")
        while time.monotonic() < until:
            await _req(c, st, "зал", "GET", random.choice(GETS))
            await asyncio.sleep(think * random.uniform(0.7, 1.3))

async def parse_client(base: str, ip: str, until: float, st: Stats) -> None:
    async with httpx.AsyncClient(base_url=base, headers={"X-Real-IP": ip}, timeout=10) as c:
        await _req(c, st, "разбор", "GET", "/auth/me")
        while time.monotonic() < until:
            await _req(c, st, "разбор", "POST", "/intake/parse", json={"text": random.choice(PHRASES)})
            await asyncio.sleep(random.uniform(0.8, 1.2))

async def flood(base: str, until: float, st: Stats, conc: int) -> None:
    limits = httpx.Limits(max_connections=conc)
    async with httpx.AsyncClient(base_url=base, headers={"X-Real-IP": "203.0.113.66"}, timeout=10, limits=limits) as c:
        async def worker() -> None:
            while time.monotonic() < until:
                c.cookies.clear()
                await _req(c, st, "поток", "GET", random.choice(GETS[:3]))
        await asyncio.gather(*(worker() for _ in range(conc)))

def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]

def report(st: Stats, seconds: int, args) -> str:
    lines = [f"Длительность {seconds} с; клиенты: зал {args.hall} (5 IP), разбор {args.parse}, поток {args.flood} "
             f"параллельных без cookie; пауза зала {args.think} с.", "",
             "| фаза | запросов | 2xx | 429 | 4xx прочие | 5xx | p50 ok, мс | p95 ok, мс | p95 все, мс |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for phase in ("зал", "разбор", "поток"):
        cnt = st.codes[phase]
        total = sum(cnt.values())
        ok = sum(v for k, v in cnt.items() if 200 <= k < 300)
        r429 = cnt.get(429, 0)
        r5 = sum(v for k, v in cnt.items() if k >= 500)
        other4 = total - ok - r429 - r5
        oklat = st.lat[phase + ":ok"]
        alllat = oklat + st.lat[phase + ":other"]
        lines.append(f"| {phase} | {total} | {ok} | {r429} | {other4} | {r5} | {pct(oklat, 50):.0f} | "
                     f"{pct(oklat, 95):.0f} | {pct(alllat, 95):.0f} |")
    if st.errors:
        lines += ["", "Сетевые ошибки клиента: " + ", ".join(f"{k} × {v}" for k, v in st.errors.items())]
    hall = st.lat["зал:ok"]
    if hall:
        lines += ["", f"Зал: среднее {statistics.mean(hall):.0f} мс, максимум {max(hall):.0f} мс, "
                      f"{sum(st.codes['зал'].values()) / seconds:.1f} запросов/с."]
    return "\n".join(lines)

async def main_async(args) -> str:
    until = time.monotonic() + args.seconds
    st = Stats()
    tasks = [hall_client(args.base, f"198.51.100.{i // 10 + 1}", until, args.think, st) for i in range(args.hall)]
    tasks += [parse_client(args.base, f"192.0.2.{i + 1}", until, st) for i in range(args.parse)]
    if args.flood:
        tasks.append(flood(args.base, until, st, args.flood))
    await asyncio.gather(*tasks)
    return report(st, args.seconds, args)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--hall", type=int, default=50)
    ap.add_argument("--parse", type=int, default=10)
    ap.add_argument("--flood", type=int, default=20)
    ap.add_argument("--think", type=float, default=0.6)
    ap.add_argument("--out")
    args = ap.parse_args()
    text = asyncio.run(main_async(args))
    print(text)
    if args.out:
        with open(args.out, "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")

if __name__ == "__main__":
    main()
