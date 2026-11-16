from __future__ import annotations

import json

from ..auth import context, settings
from ..auth.deps import detail
from . import accesslog, ratelimit

_SKIP_LIMITS = ("/health",)

def _cookie_header(name: str, value: str, max_age: int) -> bytes:
    parts = [f"{name}={value}", "Path=/", f"Max-Age={max_age}", "HttpOnly", "SameSite=Lax"]
    if settings.cookie_secure():
        parts.append("Secure")
    return "; ".join(parts).encode("latin-1")

async def _reply(send, status: int, body: dict, headers: list | None = None, cookie: bytes | None = None) -> None:
    raw = json.dumps({"detail": body}, ensure_ascii=False).encode()
    h = [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(raw)).encode()),
         (b"x-content-type-options", b"nosniff")] + (headers or [])
    if cookie:
        h.append((b"set-cookie", cookie))
    await send({"type": "http.response.start", "status": status, "headers": h})
    await send({"type": "http.response.body", "body": raw})

class Guard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        from starlette.requests import HTTPConnection
        conn = HTTPConnection(scope)
        ctx = context.resolve(conn)
        scope.setdefault("state", {})["ctx"] = ctx
        method, path = scope["method"], scope["path"]
        enforce = settings.enforce()
        cookie = _cookie_header(settings.PID_COOKIE, context.pid_cookie(ctx.principal_id), settings.PID_TTL_S) \
            if ctx.pid_new else None

        def log(status: int, note: str = "") -> None:
            accesslog.write(ctx.ip, ctx.level, method, path, status, note)

        if enforce and ctx.admin_bad:
            n, w = settings.limits()["auth_fail"]
            ok, retry = ratelimit.hit("auth_fail", ctx.ip, n, w)
            log(403 if ok else 429, "bad_admin_token")
            if not ok:
                return await _reply(send, 429, detail("auth_attempts", retry_after=retry, n=n),
                                    [(b"retry-after", str(retry).encode())], cookie)

        if enforce and ctx.level != "admin" and path not in _SKIP_LIMITS and method != "OPTIONS":
            lim = settings.limits()
            kind = "get" if method in ("GET", "HEAD") else "post"
            checks = []
            if ctx.level == "jury" or not ctx.pid_new:
                checks.append((f"{kind}_client", ctx.client_key))
            if ctx.level != "jury":
                checks.append((f"{kind}_ip", ctx.ip))
            for bucket, key in checks:
                n, w = lim[bucket]
                ok, retry = ratelimit.hit(bucket, key, n, w)
                if not ok:
                    log(429, bucket)
                    return await _reply(send, 429, detail("rate_limited", retry_after=retry, n=n, scope=bucket),
                                        [(b"retry-after", str(retry).encode())], cookie)

        if enforce and path.startswith("/intake/stt") and ctx.level == "guest":
            log(403, "stt_guest")
            return await _reply(send, 403, detail("need_jury", need="jury"), None, cookie)

        max_body = settings.MAX_AUDIO if path.startswith("/intake/stt") else settings.MAX_BODY
        clen = dict(scope.get("headers") or []).get(b"content-length")
        if clen is not None:
            try:
                too_big = int(clen) > max_body
            except ValueError:
                too_big = True
            if too_big:
                log(413, "content_length")
                return await _reply(send, 413, detail("too_large", max_bytes=max_body), None, cookie)
        recv = receive
        if method in ("POST", "PUT", "PATCH"):
            body = bytearray()
            while True:
                msg = await receive()
                if msg["type"] == "http.disconnect":
                    return
                body += msg.get("body", b"")
                if len(body) > max_body:
                    log(413, "body")
                    return await _reply(send, 413, detail("too_large", max_bytes=max_body), None, cookie)
                if not msg.get("more_body"):
                    break
            done = False

            async def recv():
                nonlocal done
                if not done:
                    done = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

        status_box = [0]

        async def send_w(msg):
            if msg["type"] == "http.response.start":
                status_box[0] = msg["status"]
                headers = list(msg.get("headers", []))
                headers.append((b"x-content-type-options", b"nosniff"))
                if cookie:
                    headers.append((b"set-cookie", cookie))
                msg = {**msg, "headers": headers}
            await send(msg)

        try:
            await self.app(scope, recv, send_w)
        except Exception:
            log(500, "exception")
            raise
        if status_box[0] >= 400:
            log(status_box[0])
