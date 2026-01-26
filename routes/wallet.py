


# routes/wallet.py
from fastapi import APIRouter, Depends
from uuid import UUID
from typing import Optional
from datetime import timezone

from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from db_exec import db_fetchall, db_fetchone
from schemas import (
    WalletListResponse, WalletItem,
    WalletBalanceResponse,
    WalletTxnPage, WalletTxnItem,
    WalletActivityPage, WalletActivityItem,
)

router = APIRouter(prefix="/v1", tags=["wallets"])


@router.get("/wallets", response_model=WalletListResponse)
def list_my_wallets(user: CurrentUser = Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        # This MUST run on same conn
        rows = db_fetchall(conn, "SELECT * FROM ledger.get_my_wallets_secure();", ())

    return WalletListResponse(
        wallets=[
            WalletItem(
                wallet_id=r[0],
                owner_id=r[1],
                owner_type=r[2],
                currency=r[3],
                country=r[4],
                account_type=r[5],
            )
            for r in rows
        ]
    )


@router.get("/wallets/{wallet_id}/balance", response_model=WalletBalanceResponse)
def wallet_balance(wallet_id: UUID, user: CurrentUser = Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        row = db_fetchone(conn, "SELECT ledger.get_available_balance_secure(%s::uuid);", (str(wallet_id),))
        bal = row[0] if row else 0

    return WalletBalanceResponse(wallet_id=wallet_id, balance_cents=int(bal))


@router.get("/wallets/{wallet_id}/transactions", response_model=WalletTxnPage)
def wallet_transactions(
    wallet_id: UUID,
    limit: int = 50,
    cursor: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        rows = db_fetchall(
            conn,
            "SELECT * FROM ledger.get_wallet_transactions_secure(%s::uuid, %s::int, %s::text);",
            (str(wallet_id), int(limit), cursor),
        )

    items = [
        WalletTxnItem(
            entry_id=r[0],
            transaction_id=r[1],
            dc=r[2],
            amount_cents=int(r[3]),
            memo=r[4],
            created_at=r[5],
        )
        for r in rows
    ]

    next_cursor = None
    if items:
        last = items[-1]
        created_at = last.created_at
        if getattr(created_at, "tzinfo", None) is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = created_at.astimezone(timezone.utc)
        next_cursor = f"{created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}|{last.entry_id}"

    return WalletTxnPage(wallet_id=wallet_id, items=items, next_cursor=next_cursor)


@router.get("/wallets/{wallet_id}/activity", response_model=WalletActivityPage)
def wallet_activity(
    wallet_id: UUID,
    limit: int = 50,
    cursor: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        rows = db_fetchall(
            conn,
            "SELECT * FROM ledger.get_wallet_activity_secure(%s::uuid, %s::int, %s::text);",
            (str(wallet_id), int(limit), cursor),
        )

    items = [
        WalletActivityItem(
            transaction_id=r[0],
            created_at=r[1],
            direction=r[2],
            amount_cents=int(r[3]),
            net_cents=int(r[4]),
            memo=r[5],
        )
        for r in rows
    ]

    next_cursor = None
    if items:
        last = items[-1]
        created_at = last.created_at
        if getattr(created_at, "tzinfo", None) is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = created_at.astimezone(timezone.utc)
        next_cursor = f"{created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}|{last.transaction_id}"

    return WalletActivityPage(wallet_id=wallet_id, items=items, next_cursor=next_cursor)
