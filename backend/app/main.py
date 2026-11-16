from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PACKAGES = ["intake", "mandate", "gate", "signing", "book", "clearing", "explain",
            "escrow", "market", "radar", "audit", "demo", "plant"]

def _warm_up() -> None:
    try:
        from .intake import service
        service.parse("200 тонн цемента в Наманган не дороже 1000000", "ru", allow_llm=False)
    except Exception:
        pass

@asynccontextmanager
async def lifespan(_app: FastAPI):
    from .demo import scenario
    from .middleware import autoclose
    scenario.reset(1)
    await asyncio.to_thread(_warm_up)
    task = autoclose.start()
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

def create_app() -> FastAPI:
    from .auth import settings
    from .middleware.cache import ResponseCache
    from .middleware.guard import Guard

    prod = settings.is_prod()
    app = FastAPI(title="UZEX Intent", version="0.1.0", lifespan=lifespan,
                  docs_url=None if prod else "/docs", redoc_url=None if prod else "/redoc",
                  openapi_url=None if prod else "/openapi.json")
    app.add_middleware(ResponseCache)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins(), allow_credentials=True,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Admin-Token"])
    app.add_middleware(Guard)

    from .auth.router import router as auth_router
    app.include_router(auth_router)
    for name in PACKAGES:
        mod = importlib.import_module(f"app.{name}.router")
        app.include_router(mod.router)

    @app.get("/health")
    def health() -> dict:
        from . import config
        return {"ok": True, "offline": config.offline(), "seed": config.DEMO_SEED, "protected": settings.enforce()}

    _FW = {
        404: ("not_found", "Такого адреса нет", "Bunday manzil yoʻq"),
        405: ("method_not_allowed", "Этот адрес не принимает такой запрос", "Bu manzil bunday soʻrovni qabul qilmaydi"),
        413: ("too_large", "Запрос слишком большой", "Soʻrov juda katta"),
        415: ("unsupported", "Неподдерживаемый формат запроса", "Qoʻllab-quvvatlanmaydigan format"),
    }

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if exc.status_code in _FW and (detail is None or isinstance(detail, str) and not any("Ѐ" <= ch <= "ӿ" for ch in detail)):
            code, ru, uz = _FW[exc.status_code]
            detail = {"code": code, "message": ru, "message_uz": uz}
        return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        errs = exc.errors()
        fields = sorted({".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query", "path")) for e in errs})
        fields = [f for f in fields if f]
        json_bad = any(e.get("type") == "json_invalid" for e in errs)
        ru = "Запрос не удалось прочитать: это не корректный JSON" if json_bad else (
            "Проверьте поля: " + ", ".join(fields) if fields else "Проверьте данные запроса")
        uz = "Soʻrovni oʻqib boʻlmadi: JSON notoʻgʻri" if json_bad else (
            "Maydonlarni tekshiring: " + ", ".join(fields) if fields else "Soʻrov maʼlumotlarini tekshiring")
        safe = [{"loc": e.get("loc"), "type": e.get("type"), "msg": e.get("msg")} for e in errs]
        return JSONResponse({"detail": {"code": "invalid_request", "message": ru, "message_uz": uz, "errors": safe}},
                            status_code=422)

    return app

app = create_app()
