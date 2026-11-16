from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from ..auth import deps, settings
from ..auth.context import Ctx
from . import parser_llm, service, stt

router = APIRouter(prefix="/intake", tags=["intake"])

class ParseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Optional[str] = ""
    lang: Optional[str] = None
    lang_hint: Optional[str] = None

@router.post("/parse")
def parse(body: ParseIn, c: Ctx = Depends(deps.ctx)) -> dict:
    hint = body.lang or body.lang_hint
    if settings.enforce() and c.level == "guest":
        deps.take("parse_guest", c.client_key, "parse_limit")
    text = body.text or ""
    cut = len(text) > settings.MAX_PHRASE
    allow_llm = deps.llm_allowed(c)
    parser_llm.take_attempted()
    out = service.parse(text[:settings.MAX_PHRASE], hint if hint in ("ru", "uz") else None, allow_llm=allow_llm)
    attempted = parser_llm.take_attempted()
    if cut:
        out.setdefault("hints", []).append("text_truncated")
    if settings.enforce() and not allow_llm:
        out.setdefault("hints", []).append("llm_limit")
    if settings.enforce() and (attempted or out.get("source") not in (None, "offline")):
        deps.llm_spent(c)
    return out

@router.post("/stt")
async def speech_to_text(request: Request, lang: Optional[str] = None,
                         c: Ctx = Depends(deps.require_level("jury"))) -> dict:
    if settings.enforce() and c.level == "jury":
        deps.take("stt_code_hour", c.code_key or c.client_key, "stt_limit")
    audio = b""
    filename = "audio.webm"
    ctype = request.headers.get("content-type", "")
    try:
        if ctype.startswith("multipart/form-data"):
            form = await request.form()
            up = form.get("audio") or form.get("file")
            if up is not None and hasattr(up, "read"):
                audio = await up.read()
                filename = getattr(up, "filename", None) or filename
            lang = lang or (form.get("lang") if isinstance(form.get("lang"), str) else None)
        else:
            audio = await request.body()
    except Exception:
        return {"transcript": "", "lang": lang, "source": "none", "error": "bad_request"}
    return await run_in_threadpool(stt.transcribe, audio, lang, filename)
