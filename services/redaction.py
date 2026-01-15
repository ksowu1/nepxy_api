from __future__ import annotations

import re
from typing import Any


_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_RE = re.compile(r"\+\d{6,15}")

_SENSITIVE_KEY_MARKERS = (
    "token",
    "authorization",
    "secret",
    "signature",
    "password",
)


def _mask_email(match: re.Match) -> str:
    first = match.group(1)
    domain = match.group(3)
    return f"{first}***{domain}"


def _mask_phone(value: str) -> str:
    if len(value) <= 8:
        return value
    prefix = value[:6]
    suffix = value[-2:]
    return f"{prefix}****{suffix}"


def redact_text(value: str) -> str:
    masked = _EMAIL_RE.sub(_mask_email, value)

    def _phone_replace(match: re.Match) -> str:
        return _mask_phone(match.group(0))

    masked = _PHONE_RE.sub(_phone_replace, masked)

    for marker in ("access_token", "refresh_token", "bearer"):
        if marker in masked.lower():
            return "[REDACTED]"

    return masked


def _is_sensitive_key(key: str) -> bool:
    key_l = (key or "").lower()
    return any(marker in key_l for marker in _SENSITIVE_KEY_MARKERS)


def redact_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return redact_dict(value)
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    return value


def redact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if _is_sensitive_key(k):
            out[k] = "[REDACTED]"
        else:
            out[k] = redact_value(v)
    return out
