

# tests/test_p2p.py
import uuid
import pytest


def _auth_headers(token: str, idem: str | None = None):
    h = {"Authorization": f"Bearer {token}"}
    if idem is not None:
        h["Idempotency-Key"] = idem
    return h


def _get_balance(client, token: str, wallet_id: str) -> int:
    r = client.get(f"/v1/wallets/{wallet_id}/balance", headers=_auth_headers(token))
    assert r.status_code == 200, f"balance failed: {r.status_code} {r.text}"
    return int(r.json()["balance_cents"])


def _cash_in_momo_best_effort(client, token: str, wallet_id: str, amount_cents: int, country: str = "TG") -> bool:
    """
    Best-effort cash-in so tests are deterministic.
    Adjust payload keys if your endpoint differs.
    """
    provider_ref = f"pytest-cashin-{uuid.uuid4()}"
    payload = {
        "user_account_id": wallet_id,
        "amount_cents": amount_cents,
        "country": country,
        "provider_ref": provider_ref,
    }
    r = client.post("/v1/cash-in/momo", json=payload, headers=_auth_headers(token, idem=provider_ref))
    return r.status_code in (200, 201)


def test_p2p_requires_idempotency_key_409(client, user1, user2, wallet1_xof, wallet2_xof):
    payload = {
        "from_wallet_id": wallet2_xof,
        "to_wallet_id": wallet1_xof,
        "amount_cents": 100,
        "memo": "pytest missing idem",
    }
    r = client.post("/v1/p2p/transfer", json=payload, headers=_auth_headers(user2.token))
    assert r.status_code == 409, r.text
    detail = (r.json() or {}).get("detail", "")
    assert "IDEMPOTENCY" in detail or "CONFLICT" in detail or detail != ""


def test_p2p_success_and_idempotency_replay(client, user1, user2, wallet1_xof, wallet2_xof):
    # Ensure sender has funds (deterministic)
    sender_before = _get_balance(client, user2.token, wallet2_xof)
    if sender_before < 500:
        topped = _cash_in_momo_best_effort(client, user2.token, wallet2_xof, 5000)
        if not topped:
            pytest.skip("Sender wallet insufficient and cash-in endpoint didn't accept payload. Fix cash-in test helper payload.")
        sender_before = _get_balance(client, user2.token, wallet2_xof)

    receiver_before = _get_balance(client, user1.token, wallet1_xof)

    idem = f"pytest-p2p-idem-{uuid.uuid4()}"
    payload = {
        "from_wallet_id": wallet2_xof,
        "to_wallet_id": wallet1_xof,
        "amount_cents": 100,
        "memo": "pytest p2p",
    }

    # First post
    r1 = client.post("/v1/p2p/transfer", json=payload, headers=_auth_headers(user2.token, idem=idem))
    assert r1.status_code == 200, r1.text
    tx1 = r1.json()["transaction_id"]

    sender_after_1 = _get_balance(client, user2.token, wallet2_xof)
    receiver_after_1 = _get_balance(client, user1.token, wallet1_xof)

    # Receiver must increase by amount
    assert receiver_after_1 == receiver_before + 100

    # Sender must decrease by at least amount (fees may exist now or later)
    assert sender_after_1 <= sender_before - 100

    # Replay (same idempotency key) => same tx + NO additional balance change
    r2 = client.post("/v1/p2p/transfer", json=payload, headers=_auth_headers(user2.token, idem=idem))
    assert r2.status_code == 200, r2.text
    tx2 = r2.json()["transaction_id"]
    assert tx1 == tx2

    sender_after_2 = _get_balance(client, user2.token, wallet2_xof)
    receiver_after_2 = _get_balance(client, user1.token, wallet1_xof)

    assert sender_after_2 == sender_after_1
    assert receiver_after_2 == receiver_after_1


def test_p2p_not_owner_forbidden_403(client, user2, wallet1_xof, wallet2_xof):
    # user2 tries to spend from user1 wallet -> must be 403 in current stable design
    payload = {
        "from_wallet_id": wallet1_xof,
        "to_wallet_id": wallet2_xof,
        "amount_cents": 50,
        "memo": "pytest should fail",
    }
    idem = f"pytest-p2p-ownerfail-{uuid.uuid4()}"
    r = client.post("/v1/p2p/transfer", json=payload, headers=_auth_headers(user2.token, idem=idem))
    assert r.status_code == 403, r.text


def test_p2p_insufficient_funds_returns_409(client, user1, user2, wallet1_xof, wallet2_xof):
    payload = {
        "from_wallet_id": wallet2_xof,
        "to_wallet_id": wallet1_xof,
        "amount_cents": 999_999_999,
        "memo": "pytest insufficient",
    }
    idem = f"pytest-p2p-insufficient-{uuid.uuid4()}"
    r = client.post("/v1/p2p/transfer", json=payload, headers=_auth_headers(user2.token, idem=idem))
    assert r.status_code == 409, r.text

    detail = (r.json() or {}).get("detail", "")
    assert (
        "INSUFFICIENT_FUNDS" in detail
        or "Insufficient" in detail
        or "DB_ERROR" in detail
        or detail != ""
    )
