

# services/db_errors.py
from __future__ import annotations

import re
from fastapi import HTTPException

DB_ERROR_HTTP_MAP: dict[str, tuple[int, str]] = {
    "WALLET_NOT_FOUND": (404, "Wallet not found"),
    "WALLET_NOT_OWNED": (403, "Forbidden"),
    "UNAUTHORIZED_WALLET_ACCESS": (403, "Forbidden"),
    "LIMIT_EXCEEDED": (429, "Limit exceeded"),
    "IDEMPOTENCY_CONFLICT": (409, "Duplicate request"),
    "INVALID_AMOUNT": (422, "Invalid amount"),
    "RATE_NOT_FOUND": (404, "Rate not found"),
    "QUOTE_NOT_FOUND": (404, "Quote not found"),
    "QUOTE_EXPIRED": (409, "Quote expired"),
    "QUOTE_NOT_EXECUTABLE": (409, "Quote not executable"),
    "POOL_NOT_CONFIGURED": (500, "FX pool not configured"),
    "INSUFFICIENT_FUNDS": (409, "Insufficient funds"),
    "FX_CONVERT_FAILED": (500, "FX convert failed"),
    "CASHIN_FAILED": (500, "Cash-in failed"),

}

# word-boundary match (avoids substring mistakes)
_DB_ERROR_PATTERN = re.compile(r"\b(" + "|".join(map(re.escape, DB_ERROR_HTTP_MAP.keys())) + r")\b")


def _extract_code_from_text(text: str) -> str | None:
    if not text:
        return None

    # Preferred format: "DB_ERROR: CODE"
    # Also supports: "DB_ERROR: P2P_FAILED (42501): WALLET_NOT_OWNED"
    if "DB_ERROR:" in text:
        tail = text.split("DB_ERROR:", 1)[1].strip()

        # 1) If any known business code appears anywhere in the tail, prefer that.
        m = _DB_ERROR_PATTERN.search(tail)
        if m:
            return m.group(1)

        # 2) Otherwise fall back to the first token (older style)
        first = tail.split()[0].strip(":").strip()
        if "(" in first:
            first = first.split("(", 1)[0]
        return first


    # Fallback: any known code in text
    m = _DB_ERROR_PATTERN.search(text)
    if m:
        return m.group(1)

    return None


def _extract_code(exc: Exception) -> str | None:
    """
    Extract DB error code from:
    - str(exc)
    - psycopg2 exception diagnostics (message_primary / message_detail)
    """
    # 1) try normal string first
    code = _extract_code_from_text(str(exc))
    if code:
        return code

    # 2) try psycopg2 diagnostic fields if present
    diag = getattr(exc, "diag", None)
    if diag is not None:
        # message_primary often contains the RAISE EXCEPTION string
        for attr in ("message_primary", "message_detail", "message_hint", "context"):
            val = getattr(diag, attr, None)
            if isinstance(val, str) and val:
                code = _extract_code_from_text(val)
                if code:
                    return code

    return None


def raise_http_from_db_error(exc: Exception) -> None:
    """
    Backward-compatible name used across the codebase.
    Convert known DB errors into HTTP responses; otherwise fail closed.
    """
    code = _extract_code(exc)
    if code and code in DB_ERROR_HTTP_MAP:
        status, message = DB_ERROR_HTTP_MAP[code]
        raise HTTPException(status_code=status, detail=message)

    raise HTTPException(status_code=500, detail="Internal server error")


# Optional alias for newer name (if some modules import this)
raise_for_db_error = raise_http_from_db_error
