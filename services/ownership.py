

# services/ownership.py
from fastapi import HTTPException
from uuid import UUID

from db import get_conn


def require_wallet_account(wallet_id: UUID) -> None:
    """
    Ensures the account exists and is a WALLET account_type.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM ledger.ledger_accounts
                WHERE id = %s::uuid
                  AND account_type = 'WALLET'
                """,
                (str(wallet_id),),
            )
            if not cur.fetchone():
                # Don't reveal whether the ID exists but is not a wallet
                raise HTTPException(status_code=404, detail="WALLET_NOT_FOUND")


def require_wallet_owned_by_user(wallet_id: UUID, user_id: UUID) -> None:
    """
    Ensures the wallet exists, is a WALLET, and belongs to the given USER.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM ledger.ledger_accounts
                WHERE id = %s::uuid
                  AND account_type = 'WALLET'
                  AND owner_type = 'USER'
                  AND owner_id = %s::uuid
                """,
                (str(wallet_id), str(user_id)),
            )
            if cur.fetchone():
                return

    # Decide if it's 404 vs 403:
    # - If the wallet exists (as a WALLET) but isn't owned by this user => 403
    # - Else => 404
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM ledger.ledger_accounts
                WHERE id = %s::uuid
                  AND account_type = 'WALLET'
                """,
                (str(wallet_id),),
            )
            if cur.fetchone():
                raise HTTPException(status_code=403, detail="WALLET_NOT_OWNED")

    raise HTTPException(status_code=404, detail="WALLET_NOT_FOUND")


def require_merchant_wallet(wallet_id: UUID) -> None:
    """
    Ensures the wallet exists, is a WALLET, and is owned by a MERCHANT.

    Uses 404 for non-merchant wallets to avoid leaking account type/ownership.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM ledger.ledger_accounts
                WHERE id = %s::uuid
                  AND account_type = 'WALLET'
                  AND owner_type = 'MERCHANT'
                """,
                (str(wallet_id),),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="MERCHANT_WALLET_NOT_FOUND")

