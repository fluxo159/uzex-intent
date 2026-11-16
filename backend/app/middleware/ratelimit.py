from __future__ import annotations

import math
import threading
import time
from collections import deque

_LOCK = threading.Lock()
_B: dict[tuple[str, str], deque] = {}
_calls = 0

def _gc(now: float) -> None:
    dead = [k for k, dq in _B.items() if not dq or now - dq[-1] > 86400]
    for k in dead:
        _B.pop(k, None)

def hit(bucket: str, key: str, limit: int, window_s: int, now: float | None = None) -> tuple[bool, int]:
    global _calls
    if limit <= 0:
        return True, 0
    now = time.monotonic() if now is None else now
    with _LOCK:
        _calls += 1
        if _calls % 5000 == 0:
            _gc(now)
        dq = _B.get((bucket, key))
        if dq is None or dq.maxlen != limit:
            dq = _B[(bucket, key)] = deque(dq or (), maxlen=limit)
        while dq and now - dq[0] >= window_s:
            dq.popleft()
        if len(dq) >= limit:
            return False, max(1, math.ceil(window_s - (now - dq[0])))
        dq.append(now)
        return True, 0

def check(bucket: str, key: str, limit: int, window_s: int, now: float | None = None) -> tuple[bool, int]:
    if limit <= 0:
        return True, 0
    now = time.monotonic() if now is None else now
    with _LOCK:
        dq = _B.get((bucket, key))
        if not dq:
            return True, 0
        n = sum(1 for t in dq if now - t < window_s)
        if n >= limit:
            oldest = next(t for t in dq if now - t < window_s)
            return False, max(1, math.ceil(window_s - (now - oldest)))
        return True, 0

def remaining(bucket: str, key: str, limit: int, window_s: int, now: float | None = None) -> int:
    if limit <= 0:
        return -1
    now = time.monotonic() if now is None else now
    with _LOCK:
        dq = _B.get((bucket, key)) or ()
        return max(0, limit - sum(1 for t in dq if now - t < window_s))

def snapshot() -> dict:
    now = time.monotonic()
    with _LOCK:
        out: dict[str, list] = {}
        for (bucket, key), dq in _B.items():
            out.setdefault(bucket, []).append((key, len(dq), round(now - dq[-1]) if dq else None))
    return {b: {"keys": len(v), "top": [{"key": k, "n": n, "last_s_ago": a}
                                         for k, n, a in sorted(v, key=lambda x: -x[1])[:10]]}
            for b, v in out.items()}

def reset() -> None:
    with _LOCK:
        _B.clear()
