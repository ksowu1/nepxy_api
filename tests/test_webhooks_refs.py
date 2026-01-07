


# tests/test_webhooks_refs.py

import uuid
import os
import json
import hmac
import hashlib



def _idem() -> str:
    return str(uuid.uuid4())


def _auth(token: str, idem: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def _cash_in(client, token: str, wallet_id: str, amount_cents: int, provider: str = "TMONEY") -> None:
    """
    Best-effort fund wallet so cash-out can succeed.
    """
    provider_ref = f"pytest-cashin-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "TG",
        "provider_ref": provider_ref,
        "provider": provider,
    }
    r = client.post("/v1/cash-in/mobile-money", json=payload, headers=_auth(token, idem=provider_ref))
    assert r.status_code in (200, 201), f"cash-in failed: {r.status_code} {r.text}"


def _cash_out(client, token: str, wallet_id: str, amount_cents: int, provider: str = "TMONEY") -> str:
    provider_ref = f"cashout-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "TG",
        "provider_ref": provider_ref,
        "provider": provider,
        "phone_e164": "+22890009911",
    }
    r = client.post("/v1/cash-out/mobile-money", json=payload, headers=_auth(token, idem=_idem()))
    assert r.status_code in (200, 201), f"cash-out failed: {r.status_code} {r.text}"
    tx = r.json().get("transaction_id")
    assert tx, "missing transaction_id"
    return tx


def _get_payout(client, token: str, tx_id: str) -> dict:
    r = client.get(f"/v1/payouts/{tx_id}", headers=_auth(token))
    assert r.status_code == 200, f"get payout failed: {r.status_code} {r.text}"
    return r.json()


def _post_webhook(client, path: str, payload: dict, expect_status: int = 200) -> dict:
    provider = _provider_from_path(path)

    # IMPORTANT: signature must match exact bytes sent
    raw = json.dumps(payload, separators=(",", ":"))
    sig = _sign(provider, raw)

    r = client.post(
        path,
        content=raw,  # send raw JSON bytes/text to match HMAC
        headers={
            "Content-Type": "application/json",
            "X-Signature": sig,
        },
    )
    assert r.status_code == expect_status, f"webhook failed: {r.status_code} {r.text}"
    return r.json()



def test_webhook_updates_by_provider_ref(client, user1, wallet1_xof):
    _cash_in(client, user1.token, wallet1_xof, amount_cents=2000, provider="TMONEY")
    tx_id = _cash_out(client, user1.token, wallet1_xof, amount_cents=100, provider="TMONEY")

    p = _get_payout(client, user1.token, tx_id)
    assert p["status"] in ("PENDING", "SENT", "RETRY")

    payload = {"provider_ref": p["provider_ref"], "status": "SUCCESS"}
    resp = _post_webhook(client, "/v1/webhooks/tmoney", payload)

    assert resp.get("ok") is True
    assert resp.get("provider") == "TMONEY"
    assert resp.get("provider_ref") == p["provider_ref"]
    assert resp.get("mapped_status") in (None, "CONFIRMED")  # depending on your response shape

    p2 = _get_payout(client, user1.token, tx_id)
    assert p2["status"] == "CONFIRMED"
    assert p2["provider_ref"] == p["provider_ref"]


def test_webhook_updates_by_external_ref_fallback(client, user1, wallet1_xof):
    _cash_in(client, user1.token, wallet1_xof, amount_cents=2000, provider="TMONEY")
    tx_id = _cash_out(client, user1.token, wallet1_xof, amount_cents=100, provider="TMONEY")

    p = _get_payout(client, user1.token, tx_id)
    assert p["status"] in ("PENDING", "SENT", "RETRY")
    assert p.get("external_ref"), "external_ref missing from payout response"

    payload = {"external_ref": p["external_ref"], "status": "SUCCESS"}
    resp = _post_webhook(client, "/v1/webhooks/tmoney", payload)

    assert resp.get("ok") is True
    assert resp.get("provider") == "TMONEY"
    assert resp.get("external_ref") == p["external_ref"]

    p2 = _get_payout(client, user1.token, tx_id)
    assert p2["status"] == "CONFIRMED"
    assert p2["external_ref"] == p["external_ref"]


def test_webhook_unknown_ref_is_ignored_200(client):
    """
    Updated behavior: webhook should NOT 404 on unknown refs (avoid provider retry storms).
    It should return 200 with ok=true + ignored=true + reason=PAYOUT_NOT_FOUND.
    """
    payload = {"external_ref": f"cashout-{uuid.uuid4()}", "status": "SUCCESS"}
    resp = _post_webhook(client, "/v1/webhooks/tmoney", payload, expect_status=200)

    assert resp.get("ok") is True
    assert resp.get("ignored") is True
    assert resp.get("reason") == "PAYOUT_NOT_FOUND"


def test_webhook_accepts_wrapped_data_object(client, user1, wallet1_xof):
    """
    Some providers send payloads like {"data": {...}}.
    """
    _cash_in(client, user1.token, wallet1_xof, amount_cents=2000, provider="TMONEY")
    tx_id = _cash_out(client, user1.token, wallet1_xof, amount_cents=100, provider="TMONEY")

    p = _get_payout(client, user1.token, tx_id)
    assert p.get("external_ref")

    payload = {"data": {"external_ref": p["external_ref"], "status": "SUCCESS"}}
    resp = _post_webhook(client, "/v1/webhooks/tmoney", payload)

    assert resp.get("ok") is True

    p2 = _get_payout(client, user1.token, tx_id)
    assert p2["status"] == "CONFIRMED"


def test_flooz_webhook_accepts_external_ref_and_confirms(client, user1, wallet1_xof):
    _cash_in(client, user1.token, wallet1_xof, amount_cents=2000, provider="TMONEY")
    tx_id = _cash_out(client, user1.token, wallet1_xof, amount_cents=100, provider="TMONEY")

    p = _get_payout(client, user1.token, tx_id)
    assert p["status"] in ("PENDING", "SENT", "RETRY")
    assert p.get("external_ref")

    payload = {"external_ref": p["external_ref"], "status": "SUCCESS"}
    resp = _post_webhook(client, "/v1/webhooks/flooz", payload)

    assert resp.get("ok") is True
    assert resp.get("provider") == "FLOOZ"

    p2 = _get_payout(client, user1.token, tx_id)
    assert p2["status"] == "CONFIRMED"


def test_momo_webhook_accepts_external_ref_and_confirms(client, user1, wallet1_xof):
    _cash_in(client, user1.token, wallet1_xof, amount_cents=2000, provider="TMONEY")
    tx_id = _cash_out(client, user1.token, wallet1_xof, amount_cents=100, provider="TMONEY")

    p = _get_payout(client, user1.token, tx_id)
    assert p["status"] in ("PENDING", "SENT", "RETRY")
    assert p.get("external_ref")

    payload = {"external_ref": p["external_ref"], "status": "SUCCESS"}
    resp = _post_webhook(client, "/v1/webhooks/momo", payload)

    assert resp.get("ok") is True
    assert resp.get("provider") == "MOMO"

    p2 = _get_payout(client, user1.token, tx_id)
    assert p2["status"] == "CONFIRMED"


def _sign(provider: str, raw_body: str) -> str:
    secret = os.getenv(f"{provider}_WEBHOOK_SECRET")
    assert secret, f"Missing {provider}_WEBHOOK_SECRET in test env"
    mac = hmac.new(secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _provider_from_path(path: str) -> str:
    if path.endswith("/tmoney"):
        return "TMONEY"
    if path.endswith("/flooz"):
        return "FLOOZ"
    if path.endswith("/momo"):
        return "MOMO"
    return "TMONEY"
