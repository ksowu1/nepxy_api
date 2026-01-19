from __future__ import annotations

import os


_TRUTHY = {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if isinstance(value, str) else default


def is_invite_only_enabled() -> bool:
    return _env("INVITE_ONLY", "false").lower() in _TRUTHY


def invite_allowlist() -> set[str]:
    raw = _env("INVITE_ALLOWLIST", "")
    if not raw:
        return set()
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def is_email_allowed(email: str) -> bool:
    if not is_invite_only_enabled():
        return True
    allowlist = invite_allowlist()
    return email.strip().lower() in allowlist
