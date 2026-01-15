from __future__ import annotations

from typing import Any
from uuid import UUID

from db import get_conn


def _ledger_sum(cur, wallet_id: UUID) -> int:
    cur.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN e.dc = 'CREDIT' THEN e.amount_cents
                WHEN e.dc = 'DEBIT' THEN -e.amount_cents
                ELSE 0
            END
        ), 0)
        FROM ledger.ledger_entries e
        JOIN ledger.ledger_transactions t ON t.id = e.transaction_id
        WHERE e.account_id = %s::uuid
          AND t.status IN ('POSTED','REVERSED');
        """,
        (str(wallet_id),),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _wallet_balance_row(cur, wallet_id: UUID) -> int | None:
    cur.execute(
        "SELECT available_cents FROM ledger.wallet_balances WHERE account_id = %s::uuid;",
        (str(wallet_id),),
    )
    row = cur.fetchone()
    return None if row is None else int(row[0])


def _check_wallet_balance(cur, wallet_id: UUID) -> dict[str, Any]:
    ledger_cents = _ledger_sum(cur, wallet_id)
    balance_cents = _wallet_balance_row(cur, wallet_id)

    if balance_cents is None:
        balance_cents = ledger_cents
        balance_source = "ledger_sum"
    else:
        balance_source = "wallet_balances"

    diff_cents = int(balance_cents) - int(ledger_cents)

    return {
        "wallet_id": wallet_id,
        "balance_cents": int(balance_cents),
        "ledger_cents": int(ledger_cents),
        "diff_cents": int(diff_cents),
        "ok": diff_cents == 0,
        "balance_source": balance_source,
    }


def assert_wallet_balance_matches_ledger(wallet_id: UUID) -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            return _check_wallet_balance(cur, wallet_id)


def list_wallet_balance_invariants() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM ledger.ledger_accounts WHERE account_type = 'WALLET';"
            )
            wallet_ids = [row[0] for row in cur.fetchall()]

            for wallet_id in wallet_ids:
                items.append(_check_wallet_balance(cur, wallet_id))

    return items
