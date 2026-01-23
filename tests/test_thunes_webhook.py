from __future__ import annotations

import os
import sys

from db import get_conn


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from _webhook_signing import canonical_json_bytes, hmac_sha256_hex  # noqa: E402


def _thunes_signature(secret: str, body_bytes: bytes) -> str:
    return "sha256=" + hmac_sha256_hex(secret, body_bytes)


def test_thunes_webhook_records_event(client, monkeypatch):
    monkeypatch.setenv("THUNES_WEBHOOK_SECRET", "dev_thunes_secret")
    payload = {"external_ref": "pytest-thunes", "status": "SUCCESSFUL"}
    body_bytes = canonical_json_bytes(payload)
    headers = {
        "Content-Type": "application/json",
        "X-Signature": _thunes_signature(os.getenv("THUNES_WEBHOOK_SECRET"), body_bytes),
    }

    r = client.post("/v1/webhooks/thunes", content=body_bytes, headers=headers)
    assert r.status_code == 200, r.text

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT provider, external_ref, signature_valid
                FROM app.webhook_events
                WHERE provider = 'THUNES' AND external_ref = %s
                ORDER BY received_at DESC
                LIMIT 1;
                """,
                (payload["external_ref"],),
            )
            row = cur.fetchone()
    assert row is not None
    assert row[0] == "THUNES"
    assert row[1] == payload["external_ref"]
    assert row[2] is True


def test_thunes_webhook_invalid_signature(client, monkeypatch):
    monkeypatch.setenv("THUNES_WEBHOOK_SECRET", "dev_thunes_secret")
    payload = {"external_ref": "pytest-thunes-bad", "status": "SUCCESSFUL"}
    body_bytes = canonical_json_bytes(payload)
    headers = {
        "Content-Type": "application/json",
        "X-Signature": "sha256=deadbeef",
    }

    r = client.post("/v1/webhooks/thunes", content=body_bytes, headers=headers)
    assert r.status_code == 401, r.text
    detail = r.json().get("detail", {})
    assert detail.get("error") == "INVALID_SIGNATURE"
