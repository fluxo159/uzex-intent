from __future__ import annotations

import os
import threading
import time

from ..auth import settings

TTL = {
    "/market/chart": 60.0,
    "/market/calendar": 60.0,
    "/market/counterfactual/ai92": 60.0,
    "/clearing/history": 60.0,
    "/book/ladder": 2.0,
    "/book/tape": 2.0,
}
_MAX_ITEMS = 500
_LOCK = threading.Lock()
_C: dict[str, tuple[float, int, list, bytes]] = {}
_gen = 0

def clear() -> None:
    global _gen
    with _LOCK:
        _C.clear()
        _gen += 1

_KEEP_HEADERS = {b"content-type"}
_READ_ONLY_POST = ("/intake/", "/auth/", "/mandate/preview", "/gate/", "/explain")

def enabled() -> bool:
    v = os.environ.get("RESPONSE_CACHE", "").strip()
    return v == "1" if v else settings.enforce()

class ResponseCache:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        method = scope["method"]
        if method != "GET":
            status_box = [0]

            async def send_w(msg):
                if msg["type"] == "http.response.start":
                    status_box[0] = msg["status"]
                await send(msg)
            try:
                await self.app(scope, receive, send_w)
            finally:
                if 200 <= status_box[0] < 300 and not scope["path"].startswith(_READ_ONLY_POST):
                    clear()
            return
        ttl = TTL.get(scope["path"])
        if ttl is None or not enabled():
            return await self.app(scope, receive, send)
        key = scope["path"] + "?" + scope.get("query_string", b"").decode("latin-1")
        now = time.monotonic()
        with _LOCK:
            hit = _C.get(key)
            gen = _gen
        if hit and now - hit[0] < ttl:
            _, status, headers, body = hit
            await send({"type": "http.response.start", "status": status, "headers": headers + [(b"x-cache", b"hit")]})
            await send({"type": "http.response.body", "body": body})
            return
        start: dict = {}
        chunks: list[bytes] = []

        async def send_c(msg):
            if msg["type"] == "http.response.start":
                start.update(msg)
            elif msg["type"] == "http.response.body":
                chunks.append(msg.get("body", b""))
            await send(msg)
        await self.app(scope, receive, send_c)
        if start.get("status") == 200:
            headers = [(k, v) for k, v in start.get("headers", []) if k.lower() in _KEEP_HEADERS]
            with _LOCK:
                if gen == _gen:
                    if len(_C) >= _MAX_ITEMS:
                        _C.clear()
                    _C[key] = (now, 200, headers, b"".join(chunks))
