from __future__ import annotations

import hashlib
import os
import secrets

ACCESS_COOKIE = "intent_access"
PID_COOKIE = "intent_pid"
ADMIN_HEADER = "x-admin-token"

ACCESS_TTL_S = 24 * 3600
PID_TTL_S = 7 * 24 * 3600

_RANDOM_SECRET = secrets.token_hex(32)

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()

def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default

def is_prod() -> bool:
    return _env("ENV").lower() in ("prod", "production")

def enforce() -> bool:
    return is_prod() or _env("AUTH_ENFORCE", "0") == "1"

def secret() -> bytes:
    s = _env("AUTH_SECRET")
    if s:
        return s.encode()
    adm = _env("ADMIN_TOKEN")
    if adm:
        return hashlib.sha256(b"intent-auth:" + adm.encode()).digest()
    return _RANDOM_SECRET.encode()

def admin_token() -> str:
    t = _env("ADMIN_TOKEN")
    return t if len(t) >= 16 else ""

def normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())

def jury_codes() -> list[str]:
    return [c for c in (normalize_code(x) for x in _env("JURY_CODES").split(",")) if 4 <= len(c) <= 16]

def cookie_secure() -> bool:
    v = _env("COOKIE_SECURE")
    return v == "1" if v else is_prod()

def trust_proxy() -> bool:
    v = _env("TRUST_PROXY")
    return v == "1" if v else True

def cors_origins() -> list[str]:
    raw = _env("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]

def autoclose_min() -> int:
    return max(0, _int("AUTOCLOSE_MIN", 10 if is_prod() else 0))

def limits() -> dict[str, tuple[int, int]]:
    return {
        "get_client": (_int("RL_GET_MIN", 120), 60),
        "post_client": (_int("RL_POST_MIN", 30), 60),
        "get_ip": (_int("RL_IP_GET_MIN", 2400), 60),
        "post_ip": (_int("RL_IP_POST_MIN", 300), 60),
        "parse_guest": (_int("RL_PARSE_GUEST_MIN", 10), 60),
        "llm_code_hour": (_int("RL_LLM_CODE_HOUR", 30), 3600),
        "llm_guest_hour": (_int("RL_LLM_GUEST_HOUR", 3), 3600),
        "llm_guest_day": (_int("RL_LLM_GUEST_DAY", 120), 86400),
        "llm_total_day": (_int("RL_LLM_DAY", 300), 86400),
        "stt_code_hour": (_int("RL_STT_CODE_HOUR", 20), 3600),
        "sign_guest_hour": (_int("RL_SIGN_GUEST_HOUR", 5), 3600),
        "sign_jury_hour": (_int("RL_SIGN_JURY_HOUR", 30), 3600),
        "sign_ip_hour": (_int("RL_SIGN_IP_HOUR", 20), 3600),
        "auth_fail": (_int("RL_AUTH_FAIL", 10), 600),
    }

MAX_BODY = 64 * 1024
MAX_AUDIO = 2 * 1024 * 1024
MAX_PHRASE = 500
