import hashlib
import hmac
import json


def canonical_json_bytes(payload) -> bytes:
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def hmac_sha256_hex(secret: str, body_bytes: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()


def tmoney_sig_header(secret: str, body_bytes: bytes) -> dict[str, str]:
    return {"X-Signature": "sha256=" + hmac_sha256_hex(secret, body_bytes)}


def tmoney_signature_header(secret: str, body_bytes: bytes) -> dict[str, str]:
    return tmoney_sig_header(secret, body_bytes)
