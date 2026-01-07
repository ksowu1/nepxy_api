

# app/providers/mobile_money/http.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass
class HttpResponse:
    status_code: int
    json: Optional[dict[str, Any]]
    text: str


class HttpClient:
    def __init__(self, timeout_s: float = 20.0, follow_redirects: bool = True):
        # follow_redirects=True helps if a provider returns redirects (or you hit a / trailing slash)
        self._client = httpx.Client(timeout=timeout_s, follow_redirects=follow_redirects)

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> HttpResponse:
        r = self._client.post(url, headers=headers, json=json_body)
        if debug:
            self._debug_dump("POST", url, headers, json_body, r)
        return self._wrap(r)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        debug: bool = False,
    ) -> HttpResponse:
        r = self._client.get(url, headers=headers)
        if debug:
            self._debug_dump("GET", url, headers, None, r)
        return self._wrap(r)

    @staticmethod
    def _wrap(r: httpx.Response) -> HttpResponse:
        try:
            payload = r.json()
        except Exception:
            payload = None
        return HttpResponse(status_code=r.status_code, json=payload, text=r.text)

    @staticmethod
    def _debug_dump(method: str, url: str, headers: dict[str, str], json_body: Any, r: httpx.Response) -> None:
        # Don’t print secrets
        safe_headers = dict(headers or {})
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "REDACTED"
        if "X-Api-Key" in safe_headers:
            safe_headers["X-Api-Key"] = "REDACTED"

        print(f"[HTTP DEBUG] {method} {url}")
        print(f"[HTTP DEBUG] headers={safe_headers}")
        if json_body is not None:
            print(f"[HTTP DEBUG] json={json_body}")
        print(f"[HTTP DEBUG] -> status={r.status_code}")
        # helpful for 405 cases:
        try:
            print(f"[HTTP DEBUG] request_method={r.request.method} request_url={r.request.url}")
        except Exception:
            pass
        print(f"[HTTP DEBUG] text={r.text[:300]}")
        if r.headers.get("allow"):
            print(f"[HTTP DEBUG] allow={r.headers.get('allow')}")


def is_retryable_http(code: int) -> bool:
    # Retry transient / throttling / gateway issues
    return code in (408, 425, 429, 500, 502, 503, 504)
