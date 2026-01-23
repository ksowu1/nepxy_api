

import hmac
import hashlib
import json
import uuid

from db import get_conn


def _sign(body_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _cash_in(client, token: str, wallet_id: str, amount_cents: int, provider: str = "TMONEY") -> None:
    provider_ref = f"pytest-cashin-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "TG",
        "provider_ref": provider_ref,
        "provider": provider,
    }
    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": provider_ref},
    )
    assert r.status_code in (200, 201), f"cash-in failed: {r.status_code} {r.text}"


def _cash_out(client, token: str, wallet_id: str, amount_cents: int, provider: str = "TMONEY") -> str:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "BJ",
        "provider_ref": f"cashout-{uuid.uuid4()}",
        "provider": provider,
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"idem-{uuid.uuid4()}"},
    )
    assert r.status_code in (200, 201), f"cash-out failed: {r.status_code} {r.text}"
    tx = r.json().get("transaction_id")
    assert tx, "missing transaction_id"
    return tx


def _get_payout(client, token: str, tx_id: str) -> dict:
    r = client.get(f"/v1/payouts/{tx_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"get payout failed: {r.status_code} {r.text}"
    return r.json()


def test_webhook_event_logged_on_success(client, user1, wallet1_xof, monkeypatch):
    # Make sure secret exists for test
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")

    _cash_in(client, user1.token, wallet1_xof, amount_cents=2000, provider="TMONEY")
    tx_id = _cash_out(client, user1.token, wallet1_xof, amount_cents=100, provider="TMONEY")

    p = _get_payout(client, user1.token, tx_id)
    ext = p["external_ref"]

    # Count before
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM webhook_events WHERE provider=%s AND external_ref=%s",
                ("TMONEY", ext),
            )
            before = cur.fetchone()[0]

    body_obj = {"external_ref": ext, "status": "SUCCESS"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_tmoney")

    r = client.post(
        "/v1/webhooks/tmoney",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": sig, "X-Request-ID": "pytest-req-1"},
    )
    assert r.status_code == 200, r.text

    # Count after + verify fields
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT signature_valid, update_applied, ignored, payout_transaction_id, request_id
                FROM webhook_events
                WHERE provider=%s AND external_ref=%s
                ORDER BY received_at DESC
                LIMIT 1
                """,
                ("TMONEY", ext),
            )
            row = cur.fetchone()
            assert row, "missing webhook_events row"
            sig_valid, update_applied, ignored, payout_tx, request_id = row

            cur.execute(
                "SELECT COUNT(*) FROM webhook_events WHERE provider=%s AND external_ref=%s",
                ("TMONEY", ext),
            )
            after = cur.fetchone()[0]

    assert after == before + 1
    assert sig_valid is True
    assert payout_tx is not None
    assert request_id == "pytest-req-1"
    # depending on terminal/no-op, either applied or ignored, but NOT both True
    assert not (bool(update_applied) and bool(ignored))


def test_webhook_event_logged_on_invalid_signature_401(client, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")

    ext = f"cashout-{uuid.uuid4()}"
    body_obj = {"external_ref": ext, "status": "SUCCESS"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM webhook_events WHERE provider=%s AND external_ref=%s",
                ("TMONEY", ext),
            )
            before = cur.fetchone()[0]

    r = client.post(
        "/v1/webhooks/tmoney",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": "sha256=deadbeef", "X-Request-ID": "pytest-req-2"},
    )
    assert r.status_code == 401, r.text

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT signature_valid, signature_error, request_id
                FROM webhook_events
                WHERE provider=%s AND external_ref=%s
                ORDER BY received_at DESC
                LIMIT 1
                """,
                ("TMONEY", ext),
            )
            row = cur.fetchone()
            assert row, "missing webhook_events row"
            sig_valid, sig_err, request_id = row

            cur.execute(
                "SELECT COUNT(*) FROM webhook_events WHERE provider=%s AND external_ref=%s",
                ("TMONEY", ext),
            )
            after = cur.fetchone()[0]

    assert after == before + 1
    assert sig_valid is False
    assert sig_err in ("MISSING_SIGNATURE", "INVALID_SIGNATURE")
    assert request_id == "pytest-req-2"
