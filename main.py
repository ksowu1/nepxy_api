

# main.py
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from routes.wallet import router as wallet_router
from routes.payments import router as payments_router
from routes.debug import router as debug_router
from routes.auth import router as auth_router
from routes.auth_google import router as auth_google_router
from routes.fx import router as fx_router
from routes.admin_ledger import router as admin_ledger_router
from routes.admin_roles import router as admin_roles_router
from routes.admin_reconcile import router as admin_reconcile_router
from routes.p2p import router as p2p_router
from routes.admin_mobile_money import router as admin_metrics_router
from routes.mock_tmoney import router as mock_tmoney_router
from routes.payouts import router as payouts_router
from routes.webhooks import router as webhooks_router
from routes.admin_webhooks import router as admin_webhooks_router
from routes.admin_support import router as admin_support_router
from routes.admin_exports import router as admin_exports_router
from routes.admin_audit import router as admin_audit_router
from routes.health import router as health_router
from routes.metrics import router as metrics_router
from routes.catalog import router as catalog_router

from app.providers.mobile_money.validate import validate_mobile_money_startup
from app.providers.mobile_money.config import mm_mode, enabled_providers, is_strict_startup_validation
from settings import validate_env_settings, settings
from middleware import (
    RequestContextMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    StagingGateMiddleware,
    MaintenanceModeMiddleware,
)

logger = logging.getLogger("nexapay")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8001


def _configure_logging_once() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _parse_csv_env(name: str, default: str = "") -> List[str]:
    raw = os.getenv(name, default) or ""
    items = [x.strip() for x in raw.split(",") if x.strip()]
    # de-dup while preserving order
    seen = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _cors_origins() -> List[str]:
    """
    Expo web + local dev can run on different ports.
    Keep this permissive in dev, tight in prod.
    Optionally override via CORS_ALLOW_ORIGINS env (comma-separated).
    """
    env_origins = _parse_csv_env("CORS_ALLOW_ORIGINS", "") or _parse_csv_env(
        settings.CORS_ALLOW_ORIGINS, ""
    )
    if env_origins:
        return env_origins

    env = (settings.ENV or "dev").lower()
    if env == "prod":
        return []

    # Common Expo + local dev origins
    return [
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:19006",
        "http://127.0.0.1:19006",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Keep your LAN IPs for testing on other devices
        "http://192.168.1.152:8081",
        "http://192.168.1.151:8081",
    ]


def _runtime_env() -> str:
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or settings.ENV or "dev").strip().lower()
    return env or "dev"


def _resolve_port() -> int:
    raw = (os.getenv("PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging_once()

    mode = (mm_mode() or "sandbox").strip().lower()
    strict = bool(is_strict_startup_validation())
    providers = sorted(enabled_providers() or [])

    validate_env_settings()

    logger.info(
        "BOOT NepXy API | host=%s | port=%s | env=%s",
        DEFAULT_HOST,
        _resolve_port(),
        settings.ENV,
    )
    logger.info(
        "BOOT NepXy API | MM_MODE=%s | MM_STRICT_STARTUP_VALIDATION=%s | MM_ENABLED_PROVIDERS=%s",
        mode,
        strict,
        ",".join(providers) if providers else "<none>",
    )

    # Provider startup validation (sandbox-friendly unless strict enabled)
    validate_mobile_money_startup()

    yield
    logger.info("SHUTDOWN NepXy API")


def create_app() -> FastAPI:
    app = FastAPI(title="NexaPay API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(StagingGateMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MaintenanceModeMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS (dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth_router)
    app.include_router(auth_google_router)

    app.include_router(wallet_router)
    app.include_router(payments_router)
    app.include_router(p2p_router)
    app.include_router(fx_router)

    app.include_router(payouts_router)
    app.include_router(webhooks_router)

    app.include_router(admin_ledger_router)
    app.include_router(admin_roles_router)
    app.include_router(admin_metrics_router)
    app.include_router(admin_webhooks_router)
    app.include_router(admin_support_router)
    app.include_router(admin_reconcile_router)
    app.include_router(admin_exports_router)
    app.include_router(admin_audit_router)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(catalog_router)

    # dev/staging helpers
    env = _runtime_env()
    staging_gate = (os.getenv("STAGING_GATE_KEY") or "").strip()
    if env in {"dev", "staging"}:
        app.include_router(debug_router)
    if env in {"dev", "staging"} or staging_gate:
        app.include_router(mock_tmoney_router)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            headers = getattr(exc, "headers", None) or {}
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)
        logger.exception("Unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
