from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def canonical_json_bytes(payload: Any) -> bytes:
    """
    Stable JSON bytes for signature calculation.
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def hmac_sha256_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def tmoney_signature_header(secret: str, body: bytes) -> dict[str, str]:
    return {"X-Signature": hmac_sha256_hex(secret, body)}


def tmoney_sig_header(secret: str, body: bytes) -> dict[str, str]:
    return tmoney_signature_header(secret, body)
