from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from . import settings

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def _mac(body: str, purpose: str) -> str:
    return _b64(hmac.new(settings.secret(), f"{purpose}|{body}".encode(), hashlib.sha256).digest())

def sign(payload: dict, ttl_s: int, purpose: str) -> str:
    body = _b64(json.dumps({**payload, "exp": int(time.time()) + ttl_s}, separators=(",", ":")).encode())
    return f"{body}.{_mac(body, purpose)}"

def verify(token: str | None, purpose: str) -> dict | None:
    if not token or len(token) > 512 or token.count(".") != 1:
        return None
    body, mac = token.split(".")
    if not hmac.compare_digest(mac, _mac(body, purpose)):
        return None
    try:
        data = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        expiry = int(data.get("exp", 0))
    except (ValueError, TypeError, OverflowError):
        return None
    if expiry < time.time():
        return None
    return data

def code_key(code: str) -> str:
    return "j" + hmac.new(settings.secret(), b"code|" + code.encode(), hashlib.sha256).hexdigest()[:12]
