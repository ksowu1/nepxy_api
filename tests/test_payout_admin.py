

# tests/test_payout_admin.py

import uuid
import pytest

from tests.conftest import _auth_headers


def test_admin_can_mark_payout_confirmed(client, admin_user, user1, wallet1_xof):
    # 1) Create a cash-out as the WALLET OWNER (user1), so ownership checks pass
    idem = f"pytest-user1-cashout-{uuid.uuid4()}"
    payload_out = {
        "user_account_id": wallet1_xof,
        "amount_cents": 100,
        "country": "TG",
        "provider_ref": f"demo-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }

    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload_out,
        headers=_auth_headers(user1.token, idem=idem),
    )
    assert r.status_code == 200, r.text
    tx_id = r.json()["transaction_id"]

    # 2) Mark payout confirmed as ADMIN
    r2 = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/confirmed",
        headers=_auth_headers(admin_user.token, idem=f"pytest-admin-{uuid.uuid4()}"),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "CONFIRMED"


def test_non_admin_cannot_mark_payout(client, user2):
    fake_tx = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        f"/v1/admin/mobile-money/payouts/{fake_tx}/confirmed",
        headers=_auth_headers(user2.token, idem=f"pytest-nonadmin-{uuid.uuid4()}"),
    )
    assert r.status_code in (401, 403), r.text
