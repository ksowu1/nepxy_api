from __future__ import annotations

import hmac
import hashlib
import json
import uuid

from fastapi.testclient import TestClient

from tests.conftest import _auth_headers, AuthedUser


def _sign(body_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _cash_out(client: TestClient, token: str, wallet_id: str) -> str:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 1000,
        "country": "BJ",
        "provider_ref": f"support-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code in (200, 201), f"cash-out failed: {r.status_code} {r.text}"
    tx = r.json().get("transaction_id")
    assert tx, "missing transaction_id"
    return tx


def _get_payout(client: TestClient, token: str, tx_id: str) -> dict:
    r = client.get(f"/v1/payouts/{tx_id}", headers=_auth_headers(token))
    assert r.status_code == 200, f"get payout failed: {r.status_code} {r.text}"
    return r.json()


def test_admin_support_search_returns_payout_and_webhook(
    client: TestClient, admin: AuthedUser, user1: AuthedUser, wallet1_xof: str, monkeypatch
):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")

    tx_id = _cash_out(client, user1.token, wallet1_xof)
    payout = _get_payout(client, user1.token, tx_id)
    external_ref = payout["external_ref"]

    body_obj = {"external_ref": external_ref, "status": "SUCCESS"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_tmoney")

    r = client.post(
        "/v1/webhooks/tmoney",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 200, r.text

    search = client.get(
        "/v1/admin/support/search",
        params={"q": external_ref},
        headers=_auth_headers(admin.token),
    )
    assert search.status_code == 200, search.text
    data = search.json()
    assert data["payouts"], "expected payout match"
    assert data["webhook_events"], "expected webhook event match"
