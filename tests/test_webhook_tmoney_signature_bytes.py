from __future__ import annotations

import os
import sys
import json

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from _webhook_signing import canonical_json_bytes, tmoney_signature_header  # noqa: E402


def test_tmoney_signature_mismatch_when_bytes_differ(client, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")
    payload = {"status": "SUCCESS", "external_ref": "pytest-ext"}

    canonical_bytes = canonical_json_bytes(payload)
    headers = tmoney_signature_header(os.getenv("TMONEY_WEBHOOK_SECRET"), canonical_bytes)
    headers["Content-Type"] = "application/json"

    altered_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=False).encode("utf-8")
    assert altered_bytes != canonical_bytes

    bad = client.post("/v1/webhooks/tmoney", content=altered_bytes, headers=headers)
    assert bad.status_code == 401, bad.text
    assert bad.json().get("detail", {}).get("error") == "INVALID_SIGNATURE"

    ok = client.post("/v1/webhooks/tmoney", content=canonical_bytes, headers=headers)
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert data.get("ok") is True
    assert data.get("provider") == "TMONEY"
