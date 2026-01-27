from __future__ import annotations

import os
import sys
import uuid

from fastapi.testclient import TestClient

from tests.conftest import _auth_headers

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from _webhook_signing import canonical_json_bytes, tmoney_signature_header  # noqa: E402


def _register_and_login(client: TestClient) -> tuple[str, str]:
    email = f"pytest-trace-{uuid.uuid4().hex[:8]}@nexapay.io"
    password = "password123"
    phone = f"+2287{str(uuid.uuid4().int)[:7]}"

    r = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "phone_e164": phone,
            "country": "TG",
            "full_name": "Trace Tester",
        },
    )
    assert r.status_code in (200, 201, 409), r.text

    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = client.get("/v1/wallets", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    wallets = r.json().get("wallets") or r.json()
    wallet_id = wallets[0]["wallet_id"] if isinstance(wallets, list) else wallets["wallet_id"]
    return token, wallet_id


def test_admin_trace_finds_payout_and_webhook(client: TestClient, admin, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")
    user_token, wallet_id = _register_and_login(client)

    # fund wallet
    r = client.post(
        "/v1/cash-in/mobile-money",
        json={
            "wallet_id": wallet_id,
            "amount_cents": 1000,
            "country": "TG",
            "provider_ref": f"trace-cashin-{uuid.uuid4()}",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
        headers=_auth_headers(user_token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text

    provider_ref = f"trace-ref-{uuid.uuid4()}"
    r = client.post(
        "/v1/cash-out/mobile-money",
        json={
            "wallet_id": wallet_id,
            "amount_cents": 100,
            "country": "BJ",
            "provider_ref": provider_ref,
            "provider": "TMONEY",
            "phone_e164": "+22890001111",
        },
        headers=_auth_headers(user_token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    transaction_id = data.get("transaction_id")
    external_ref = data.get("external_ref")

    payload = {"provider_ref": provider_ref, "external_ref": external_ref, "status": "SUCCESS"}
    body_bytes = canonical_json_bytes(payload)
    headers = tmoney_signature_header(os.getenv("TMONEY_WEBHOOK_SECRET"), body_bytes)
    headers["Content-Type"] = "application/json"

    r = client.post("/v1/webhooks/tmoney", content=body_bytes, headers=headers)
    assert r.status_code == 200, r.text

    r = client.get(
        f"/v1/admin/mobile-money/trace?transaction_id={transaction_id}",
        headers=_auth_headers(admin.token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    payouts = body.get("payouts") or []
    events = body.get("webhook_events") or []
    assert any(p.get("transaction_id") == transaction_id for p in payouts)
    assert any(e.get("provider_ref") == provider_ref for e in events)

    r = client.get(
        f"/v1/admin/mobile-money/trace?external_ref={external_ref}",
        headers=_auth_headers(admin.token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    payouts = body.get("payouts") or []
    assert any(p.get("external_ref") == external_ref for p in payouts)
