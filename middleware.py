
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

SENSITIVE_HEADERS = {"authorization", "cookie"}

def _safe_headers(headers: dict) -> dict:
    safe = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in SENSITIVE_HEADERS:
            safe[k] = "***"
        else:
            safe[k] = v
    return safe

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        start = time.time()

        # attach to request state
        request.state.request_id = req_id

        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.time() - start) * 1000)
            status = getattr(response, "status_code", 500)

            # minimal structured log line (no PII)
            print({
                "event": "http_request",
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
                "headers": _safe_headers(dict(request.headers)),
            })
