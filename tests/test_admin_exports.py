from __future__ import annotations

import csv
import io
import uuid
from datetime import date

from fastapi.testclient import TestClient

from tests.conftest import _auth_headers, AuthedUser


def _cash_out(client: TestClient, token: str, wallet_id: str) -> str:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 1000,
        "country": "BJ",
        "provider_ref": f"export-{uuid.uuid4()}",
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


def _read_csv(text: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader if row]


def test_admin_exports_csv_returns_rows(
    client: TestClient, admin: AuthedUser, user1: AuthedUser, wallet1_xof: str
):
    _cash_out(client, user1.token, wallet1_xof)
    today = date.today().isoformat()

    payouts = client.get(
        "/v1/admin/exports/payouts.csv",
        params={"from": today, "to": today},
        headers=_auth_headers(admin.token),
    )
    assert payouts.status_code == 200, payouts.text
    assert payouts.headers["content-type"].startswith("text/csv")
    rows = _read_csv(payouts.text)
    assert rows[0] == [
        "transaction_id",
        "created_at",
        "country",
        "provider",
        "status",
        "amount_cents",
        "fee_cents",
        "fx_rate",
        "receiver_phone",
        "external_ref",
        "provider_ref",
    ]
    assert len(rows) >= 2

    ledger = client.get(
        "/v1/admin/exports/ledger.csv",
        params={"from": today, "to": today},
        headers=_auth_headers(admin.token),
    )
    assert ledger.status_code == 200, ledger.text
    assert ledger.headers["content-type"].startswith("text/csv")
    ledger_rows = _read_csv(ledger.text)
    assert ledger_rows[0] == [
        "entry_id",
        "created_at",
        "account",
        "debit",
        "credit",
        "wallet_id",
        "transaction_id",
        "memo",
    ]
    assert len(ledger_rows) >= 2
