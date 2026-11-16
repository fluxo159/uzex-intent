from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..middleware import autoclose, ratelimit
from . import deps, settings, tokens
from .context import Ctx, access_cookie

router = APIRouter(prefix="/auth", tags=["auth"])

class CodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=32)

def _me(c: Ctx) -> dict:
    return {"level": c.level, "principal_id": c.principal_id, "limits_left": deps.limits_left(c),
            "llm": deps.llm_allowed(c),
            "voice": c.level != "guest" or not settings.enforce(),
            "can_close_basket": c.level == "admin" or not settings.enforce(),
            "autoclose": autoclose.info(),
            "protected": settings.enforce()}

def _set_access(resp: Response, value: str, max_age: int) -> None:
    resp.set_cookie(settings.ACCESS_COOKIE, value, max_age=max_age, httponly=True, samesite="lax",
                    secure=settings.cookie_secure(), path="/")

@router.post("/code")
def enter_code(body: CodeIn, response: Response, c: Ctx = Depends(deps.ctx)) -> dict:
    n, w = settings.limits()["auth_fail"]
    ok, retry = ratelimit.check("auth_fail", c.ip, n, w)
    if not ok:
        raise deps.too_many("auth_attempts", retry, n=n, scope="auth_fail")
    code = settings.normalize_code(body.code)
    match = next((k for k in settings.jury_codes() if hmac.compare_digest(k.encode(), code.encode())), None)
    if match is None:
        ratelimit.hit("auth_fail", c.ip, n, w)
        raise HTTPException(401, {"code": "bad_code", "message_ru": "Код не подошёл.",
                                  "message_uz": "Kod mos kelmadi."})
    key = tokens.code_key(match)
    _set_access(response, access_cookie(key), settings.ACCESS_TTL_S)
    if c.level != "admin":
        c.level, c.code_key = "jury", key
    return _me(c)

@router.get("/me")
def me(c: Ctx = Depends(deps.ctx)) -> dict:
    return _me(c)

@router.post("/logout")
def logout(response: Response, c: Ctx = Depends(deps.ctx)) -> dict:
    _set_access(response, "", 0)
    return {"level": "admin" if c.level == "admin" else "guest"}

@router.get("/limits")
def limits_view(request: Request, _c: Ctx = Depends(deps.require_level("admin"))) -> dict:
    return {"limits": {k: {"n": n, "window_s": w} for k, (n, w) in settings.limits().items()},
            "jury_codes": len(settings.jury_codes()), "buckets": ratelimit.snapshot(),
            "autoclose": autoclose.info()}
