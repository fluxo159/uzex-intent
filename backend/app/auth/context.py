from __future__ import annotations

import hmac
import ipaddress
import secrets
from dataclasses import dataclass
from typing import Literal

from starlette.requests import HTTPConnection

from . import settings, tokens

Level = Literal["guest", "jury", "admin"]
RANK = {"guest": 0, "jury": 1, "admin": 2}

@dataclass
class Ctx:
    ip: str
    level: Level
    principal_id: str
    pid_new: bool = False
    code_key: str | None = None
    admin_bad: bool = False

    @property
    def client_key(self) -> str:
        if self.code_key:
            return self.code_key
        if self.pid_new:
            return f"{self.ip}|anon"
        return f"{self.ip}|{self.principal_id}"

    @property
    def participant_key(self) -> str:
        return f"{self.ip}|anon" if self.pid_new else self.principal_id

def _local(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("testclient", "localhost")

def client_ip(conn: HTTPConnection) -> str:
    host = conn.client.host if conn.client else "0.0.0.0"
    if settings.trust_proxy() and _local(host):
        real = conn.headers.get("x-real-ip") or (conn.headers.get("x-forwarded-for") or "").split(",")[0]
        real = real.strip()
        if real:
            try:
                return str(ipaddress.ip_address(real))
            except ValueError:
                pass
    return host

def new_pid() -> str:
    return "g-" + secrets.token_hex(8)

def pid_cookie(pid: str) -> str:
    return tokens.sign({"p": pid}, settings.PID_TTL_S, "pid")

def access_cookie(code_key: str) -> str:
    return tokens.sign({"l": "jury", "c": code_key}, settings.ACCESS_TTL_S, "access")

def _jury_key(conn: HTTPConnection) -> str | None:
    data = tokens.verify(conn.cookies.get(settings.ACCESS_COOKIE), "access")
    if not data or data.get("l") != "jury":
        return None
    key = data.get("c")
    return key if key in {tokens.code_key(c) for c in settings.jury_codes()} else None

def resolve(conn: HTTPConnection) -> Ctx:
    ip = client_ip(conn)
    data = tokens.verify(conn.cookies.get(settings.PID_COOKIE), "pid")
    pid = data.get("p") if data else None
    pid_new = not (isinstance(pid, str) and pid.startswith("g-") and len(pid) <= 40)
    if pid_new:
        pid = new_pid()
    level: Level = "guest"
    admin_bad = False
    code_key = _jury_key(conn)
    if code_key:
        level = "jury"
    sent = conn.headers.get(settings.ADMIN_HEADER)
    if sent:
        tok = settings.admin_token()
        if tok and hmac.compare_digest(sent.encode(), tok.encode()):
            level = "admin"
        else:
            admin_bad = True
    return Ctx(ip=ip, level=level, principal_id=pid, pid_new=pid_new, code_key=code_key, admin_bad=admin_bad)

def get(conn: HTTPConnection) -> Ctx:
    ctx = getattr(conn.state, "ctx", None)
    if ctx is None:
        ctx = resolve(conn)
        conn.state.ctx = ctx
    return ctx
