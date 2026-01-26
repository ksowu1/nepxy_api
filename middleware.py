
import logging
import os
import time
import uuid
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from rate_limit import allow_token_bucket
from services.metrics import increment_http_requests
from settings import settings

logger = logging.getLogger("nexapay.http")


class StagingGateMiddleware(BaseHTTPMiddleware):
    ALLOWED_PATHS = {"/healthz", "/readyz", "/openapi.json"}

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        key = (os.getenv("STAGING_GATE_KEY") or "").strip()
        env = (
            (os.getenv("ENVIRONMENT") or os.getenv("ENV") or (settings.ENV or "dev"))
            .strip()
            .lower()
        )
        gate_enabled = env == "staging" and bool(key)
        path = request.url.path or ""
        if gate_enabled and not self._is_allowed_path(path):
            header = request.headers.get("X-Staging-Key")
            if header != key:
                raise HTTPException(status_code=403, detail="STAGING_GATE_KEY_REQUIRED")
        return await call_next(request)

    def _is_allowed_path(self, path: str) -> bool:
        if path in self.ALLOWED_PATHS:
            return True
        if path.startswith("/docs"):
            return True
        return False


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Request-Id")
            or str(uuid.uuid4())
        )
        start = time.time()

        # attach to request state
        request.state.request_id = req_id
        logger.info(
            "http_request_start request_id=%s method=%s path=%s",
            req_id,
            request.method,
            request.url.path,
        )

        response = None
        try:
            response = await call_next(request)
        except HTTPException as exc:
            headers = dict(getattr(exc, "headers", None) or {})
            response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)
        except Exception:
            logger.exception(
                "http_request error request_id=%s method=%s path=%s",
                req_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        finally:
            duration_ms = int((time.time() - start) * 1000)
            status = getattr(response, "status_code", 500)

            if response is not None:
                response.headers["X-Request-ID"] = req_id
                route_obj = request.scope.get("route")
                route = getattr(route_obj, "path", request.url.path)
                increment_http_requests(route, status)

            logger.info(
                "http_request_end request_id=%s status=%s duration_ms=%s",
                req_id,
                status,
                duration_ms,
            )
        return response


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not _maintenance_enabled():
            return await call_next(request)

        path = request.url.path or ""
        method = (request.method or "").upper()
        if method == "GET" and path == "/health":
            return await call_next(request)
        if path.startswith("/v1/webhooks") or path.startswith("/webhooks"):
            return await call_next(request)

        env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or settings.ENV or "dev").strip().lower()
        if env in {"dev", "staging"}:
            if path == "/openapi.json" or path.startswith("/docs"):
                return await call_next(request)

        return JSONResponse(status_code=503, content={"detail": "MAINTENANCE_MODE"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        auth_limit: int = 120,
        auth_window_seconds: int = 60,
        webhook_limit: int = 300,
        webhook_window_seconds: int = 60,
    ):
        super().__init__(app)
        self.auth_limit = int(auth_limit)
        self.auth_window_seconds = int(auth_window_seconds)
        self.webhook_limit = int(webhook_limit)
        self.webhook_window_seconds = int(webhook_window_seconds)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        group = None
        if path.startswith("/v1/auth/"):
            group = "auth"
            limit = self.auth_limit
            window = self.auth_window_seconds
        elif path.startswith("/v1/webhooks/"):
            group = "webhooks"
            limit = self.webhook_limit
            window = self.webhook_window_seconds

        if not group:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        key = f"{group}:{client}"
        refill_per_sec = float(limit) / max(1.0, float(window))
        ok = allow_token_bucket(key, capacity=limit, refill_per_sec=refill_per_sec)
        if ok:
            return await call_next(request)

        req_id = (
            getattr(request.state, "request_id", None)
            or request.headers.get("X-Request-ID")
            or request.headers.get("X-Request-Id")
            or str(uuid.uuid4())
        )
        headers = {"X-Request-ID": req_id}
        return JSONResponse(status_code=429, content={"detail": "RATE_LIMITED"}, headers=headers)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )

        if (settings.ENV or "dev").lower() == "prod":
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
            if scheme == "https":
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )

        return response


def _maintenance_enabled() -> bool:
    raw = (os.getenv("MAINTENANCE_MODE") or "0").strip().lower()
    return raw in {"1", "true"}
