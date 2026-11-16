from __future__ import annotations

import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .. import config

_log: logging.Logger | None = None
_THROTTLE_S = 10.0
_seen: dict[tuple, list] = {}
_lock = threading.Lock()

def logger() -> logging.Logger:
    global _log
    if _log is None:
        lg = logging.getLogger("intent.access")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        path = Path(os.environ.get("ACCESS_LOG", "") or (config.ROOT / "logs" / "access.log"))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            h: logging.Handler = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        except OSError:
            h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        lg.addHandler(h)
        _log = lg
    return _log

def write(ip: str, level: str, method: str, path: str, status: int, note: str = "") -> None:
    if status in (429, 413):
        now = time.monotonic()
        with _lock:
            if len(_seen) > 10_000:
                _seen.clear()
            k = (ip, status, note)
            rec = _seen.get(k)
            if rec and now - rec[0] < _THROTTLE_S:
                rec[1] += 1
                return
            skipped = rec[1] if rec else 0
            _seen[k] = [now, 0]
        if skipped:
            note = f"{note} (+{skipped} за {_THROTTLE_S:.0f} с)".strip()
    safe = path.replace("\n", " ").replace("\r", " ")[:200]
    logger().info("%s %s %s %s %d %s", ip, level, method, safe, status, note)

def reset() -> None:
    with _lock:
        _seen.clear()
