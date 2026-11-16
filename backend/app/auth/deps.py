from __future__ import annotations

import math

from fastapi import HTTPException, Request

from ..middleware import ratelimit
from . import settings
from .context import RANK, Ctx, get

MESSAGES = {
    "rate_limited": ("Слишком много запросов. Подождите {s} с и попробуйте снова.",
                     "So‘rovlar juda ko‘p. {s} soniya kuting va qayta urinib ko‘ring."),
    "parse_limit": ("Гостям — не больше {n} разборов фразы в минуту. Подождите {s} с.",
                    "Mehmonlar uchun — daqiqasiga {n} tadan ko‘p tahlil emas. {s} soniya kuting."),
    "sign_limit": ("Не больше {n} поручений в час. Следующее — через {m} мин.",
                   "Soatiga {n} tadan ko‘p topshiriq emas. Keyingisi — {m} daqiqadan so‘ng."),
    "sign_ip_limit": ("С этой сети подано слишком много поручений. Попробуйте через {m} мин.",
                      "Bu tarmoqdan juda ko‘p topshiriq berildi. {m} daqiqadan so‘ng urinib ko‘ring."),
    "stt_limit": ("Лимит голосового ввода по этому коду исчерпан. Через {m} мин или введите текстом.",
                  "Bu kod bo‘yicha ovozli kiritish limiti tugadi. {m} daqiqadan so‘ng yoki matn bilan kiriting."),
    "auth_attempts": ("Слишком много неверных попыток. Попробуйте через {m} мин.",
                      "Noto‘g‘ri urinishlar juda ko‘p. {m} daqiqadan so‘ng urinib ko‘ring."),
    "need_jury": ("Доступно по коду жюри: «Ещё → Код доступа».",
                  "Hakamlar kodi bilan ochiladi: «Yana → Kirish kodi»."),
    "need_admin": ("Только для ведущего.", "Faqat boshlovchi uchun."),
    "too_large": ("Слишком большой запрос.", "So‘rov juda katta."),
}

def detail(code: str, **params) -> dict:
    s = int(params.get("retry_after", 0) or 0)
    fmt = {"s": s, "m": max(1, math.ceil(s / 60)), **params}
    ru, uz = MESSAGES[code]
    return {"code": code, **params, "message_ru": ru.format(**fmt), "message_uz": uz.format(**fmt)}

def too_many(code: str, retry_after: int, **params) -> HTTPException:
    return HTTPException(429, detail(code, retry_after=retry_after, **params),
                         headers={"Retry-After": str(retry_after)})

def ctx(request: Request) -> Ctx:
    return get(request)

def require_level(level: str):
    def dep(request: Request) -> Ctx:
        c = get(request)
        if settings.enforce() and RANK[c.level] < RANK[level]:
            raise HTTPException(403, detail("need_admin" if level == "admin" else "need_jury", need=level))
        return c
    return dep

def take(bucket: str, key: str, code: str) -> None:
    n, w = settings.limits()[bucket]
    ok, retry = ratelimit.hit(bucket, key, n, w)
    if not ok:
        raise too_many(code, retry, n=n, scope=bucket)

def llm_allowed(c: Ctx) -> bool:
    if not settings.enforce():
        return True
    if c.level == "admin":
        return True
    lim = settings.limits()
    n2, w2 = lim["llm_total_day"]
    if not ratelimit.check("llm_total_day", "all", n2, w2)[0]:
        return False
    if c.level == "jury" and c.code_key:
        n1, w1 = lim["llm_code_hour"]
        return ratelimit.check("llm_code_hour", c.code_key, n1, w1)[0]
    n3, w3 = lim["llm_guest_hour"]
    n4, w4 = lim["llm_guest_day"]
    return (ratelimit.check("llm_guest_hour", c.participant_key, n3, w3)[0]
            and ratelimit.check("llm_guest_day", "all", n4, w4)[0])

def llm_spent(c: Ctx) -> None:
    lim = settings.limits()
    if c.level == "jury" and c.code_key:
        ratelimit.hit("llm_code_hour", c.code_key, *lim["llm_code_hour"])
    elif c.level != "admin":
        ratelimit.hit("llm_guest_hour", c.participant_key, *lim["llm_guest_hour"])
        ratelimit.hit("llm_guest_day", "all", *lim["llm_guest_day"])
    ratelimit.hit("llm_total_day", "all", *lim["llm_total_day"])

def limits_left(c: Ctx) -> dict:
    lim = settings.limits()
    rem = ratelimit.remaining
    out: dict = {}
    if c.level == "guest":
        out["parse_per_min"] = rem("parse_guest", c.client_key, *lim["parse_guest"])
        out["sign_per_hour"] = rem("sign_guest_hour", c.participant_key, *lim["sign_guest_hour"])
        out["llm_per_hour"] = rem("llm_guest_hour", c.participant_key, *lim["llm_guest_hour"])
        out["llm_today_guests"] = rem("llm_guest_day", "all", *lim["llm_guest_day"])
    elif c.level == "jury":
        out["sign_per_hour"] = rem("sign_jury_hour", c.participant_key, *lim["sign_jury_hour"])
    if c.level == "jury" and c.code_key:
        out["llm_per_hour"] = rem("llm_code_hour", c.code_key, *lim["llm_code_hour"])
        out["llm_today_all"] = rem("llm_total_day", "all", *lim["llm_total_day"])
        out["stt_per_hour"] = rem("stt_code_hour", c.code_key, *lim["stt_code_hour"])
    return out
