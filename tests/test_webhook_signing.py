from __future__ import annotations

import os
import sys


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from _webhook_signing import canonical_json_bytes, tmoney_signature_header  # noqa: E402


def test_canonical_json_bytes_stable():
    payload_a = {"b": 1, "a": 2}
    payload_b = {"a": 2, "b": 1}
    bytes_a = canonical_json_bytes(payload_a)
    bytes_b = canonical_json_bytes(payload_b)
    assert bytes_a == bytes_b
    assert bytes_a == b'{"a":2,"b":1}'


def test_tmoney_signature_matches_server(client, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")
    payload = {"external_ref": "pytest-ext", "status": "SUCCESS"}
    body_bytes = canonical_json_bytes(payload)
    headers = tmoney_signature_header(os.getenv("TMONEY_WEBHOOK_SECRET"), body_bytes)
    headers["Content-Type"] = "application/json"

    r = client.post("/v1/webhooks/tmoney", content=body_bytes, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("provider") == "TMONEY"


def test_tmoney_signature_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")
    payload = {"external_ref": "pytest-ext-wrong", "status": "SUCCESS"}
    body_bytes = canonical_json_bytes(payload)
    headers = tmoney_signature_header("wrong_secret", body_bytes)
    headers["Content-Type"] = "application/json"

    r = client.post("/v1/webhooks/tmoney", content=body_bytes, headers=headers)
    assert r.status_code == 401, r.text
    body = r.json()
    assert body.get("detail", {}).get("error") == "INVALID_SIGNATURE"
