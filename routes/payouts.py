


# routes/payouts.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from schemas import CashOutQuote

from db import get_conn
from deps.auth import get_current_user, CurrentUser

logger = logging.getLogger("nexapay")
router = APIRouter(prefix="/v1", tags=["payouts"])

PAYOUTS_ROUTE_VERSION = "payouts-2026-01-07-v7"


class PayoutItem(BaseModel):
    transaction_id: UUID
    provider: str
    phone_e164: str
    provider_ref: Optional[str] = None
    status: str
    last_error: Optional[str] = None
    retryable: bool
    attempt_count: int
    amount_cents: int
    currency: str
    created_at: str
    updated_at: str
    provider_response: Optional[Dict[str, Any]] = None


class PayoutListResponse(BaseModel):
    wallet_id: UUID
    payouts: List[PayoutItem]


class PayoutDetailResponse(BaseModel):
    transaction_id: UUID
    provider: str
    phone_e164: str
    provider_ref: Optional[str] = None
    external_ref: str
    status: str
    last_error: Optional[str] = None
    retryable: bool
    attempt_count: int
    amount_cents: int
    currency: str
    created_at: str
    updated_at: str
    provider_response: Optional[Dict[str, Any]] = None
    quote: Optional[CashOutQuote] = None


def _rollback_quiet(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def _qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _discover_wallet_table(cur) -> Tuple[str, str, str]:
    """
    Find a table/view that contains:
      - owner_id
      - and either wallet_id OR id (as wallet id)
    Prefer schema=ledger, then app; prefer tables with 'wallet' in name.
    Returns: (schema, table, wallet_id_column)
    """
    cur.execute(
        """
        WITH cols AS (
          SELECT
            table_schema,
            table_name,
            MAX(CASE WHEN column_name = 'owner_id' THEN 1 ELSE 0 END) AS has_owner,
            MAX(CASE WHEN column_name = 'wallet_id' THEN 1 ELSE 0 END) AS has_wallet_id,
            MAX(CASE WHEN column_name = 'id' THEN 1 ELSE 0 END) AS has_id
          FROM information_schema.columns
          WHERE column_name IN ('owner_id','wallet_id','id')
          GROUP BY table_schema, table_name
        )
        SELECT table_schema, table_name,
               CASE WHEN has_wallet_id = 1 THEN 'wallet_id' ELSE 'id' END AS wallet_col
        FROM cols
        WHERE has_owner = 1 AND (has_wallet_id = 1 OR has_id = 1)
        ORDER BY
          CASE
            WHEN table_schema = 'ledger' THEN 0
            WHEN table_schema = 'app' THEN 1
            ELSE 9
          END,
          CASE
            WHEN table_name ILIKE '%wallet%' THEN 0
            ELSE 1
          END,
          table_schema, table_name
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="WALLETS_TABLE_NOT_FOUND")
    return str(row[0]), str(row[1]), str(row[2])


def _assert_wallet_owned_by_user(cur, conn, wallet_id: UUID, user_id: UUID) -> None:
    """
    Ownership check without relying on DB session actor.
    """
    try:
        schema, table, wallet_col = _discover_wallet_table(cur)
        ref = f"{_qident(schema)}.{_qident(table)}"
        col = _qident(wallet_col)

        cur.execute(
            f"""
            SELECT 1
            FROM {ref}
            WHERE {col} = %s::uuid
              AND owner_id = %s::uuid
            LIMIT 1;
            """,
            (str(wallet_id), str(user_id)),
        )
        ok = cur.fetchone()
        if not ok:
            raise HTTPException(status_code=404, detail="WALLET_NOT_FOUND")

    except HTTPException:
        raise
    except Exception as e:
        _rollback_quiet(conn)
        raise HTTPException(status_code=500, detail=f"WALLET_OWNERSHIP_CHECK_FAILED: {type(e).__name__}: {e}")


def _discover_entries_table(cur) -> Tuple[str, str]:
    """
    Find one table/view that has BOTH transaction_id and wallet_id.
    Prefer schema ledger/app; prefer names containing entry/entr.
    """
    cur.execute(
        """
        WITH cols AS (
          SELECT
            table_schema,
            table_name,
            MAX(CASE WHEN column_name = 'transaction_id' THEN 1 ELSE 0 END) AS has_tx,
            MAX(CASE WHEN column_name = 'wallet_id' THEN 1 ELSE 0 END) AS has_wallet
          FROM information_schema.columns
          WHERE column_name IN ('transaction_id','wallet_id')
          GROUP BY table_schema, table_name
        )
        SELECT table_schema, table_name
        FROM cols
        WHERE has_tx = 1 AND has_wallet = 1
        ORDER BY
          CASE
            WHEN table_schema = 'ledger' THEN 0
            WHEN table_schema = 'app' THEN 1
            ELSE 9
          END,
          CASE
            WHEN table_name ILIKE '%entr%' OR table_name ILIKE '%entry%' THEN 0
            ELSE 1
          END,
          table_schema, table_name
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="LEDGER_ENTRIES_TABLE_NOT_FOUND")
    return str(row[0]), str(row[1])


def _wallet_id_for_tx(cur, entry_ref: str, tx_id: UUID) -> UUID:
    cur.execute(
        f"SELECT wallet_id FROM {entry_ref} WHERE transaction_id=%s::uuid LIMIT 1;",
        (str(tx_id),),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Payout not found")
    return UUID(str(row[0]))


@router.get("/payouts/{transaction_id}", response_model=PayoutDetailResponse)
def get_payout_by_transaction_id(
    transaction_id: UUID,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    response.headers["X-Nepxy-Payouts-Version"] = PAYOUTS_ROUTE_VERSION

    with get_conn() as conn:
        _rollback_quiet(conn)
        with conn.cursor() as cur:
            entry_schema, entry_table = _discover_entries_table(cur)
            entry_ref = f"{_qident(entry_schema)}.{_qident(entry_table)}"

            wallet_id = _wallet_id_for_tx(cur, entry_ref, transaction_id)
            _assert_wallet_owned_by_user(cur, conn, wallet_id, user.user_id)

            cur.execute(
                """
                SELECT
                  p.transaction_id,
                  p.provider,
                  p.phone_e164,
                  p.provider_ref,
                  tx.external_ref,
                  p.status,
                  p.last_error,
                  p.retryable,
                  p.attempt_count,
                  p.amount_cents,
                  p.currency,
                  p.created_at,
                  p.updated_at,
                  p.provider_response,
                  p.quote
                FROM app.mobile_money_payouts p
                LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
                WHERE p.transaction_id = %s::uuid
                LIMIT 1;
                """,
                (str(transaction_id),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Payout not found")

            provider_response = row[13]
            if provider_response is not None and not isinstance(provider_response, dict):
                provider_response = {"raw": provider_response}

            quote = row[14]
            if quote is not None and not isinstance(quote, dict):
                quote = {"raw": quote}

            external_ref = row[4] if row[4] else f"ext-{transaction_id}"

            return PayoutDetailResponse(
                transaction_id=UUID(str(row[0])),
                provider=str(row[1]),
                phone_e164=str(row[2]),
                provider_ref=(str(row[3]) if row[3] else None),
                external_ref=str(external_ref),
                status=str(row[5]),
                last_error=(str(row[6]) if row[6] else None),
                retryable=bool(row[7]),
                attempt_count=int(row[8] or 0),
                amount_cents=int(row[9] or 0),
                currency=str(row[10] or ""),
                created_at=str(row[11]),
                updated_at=str(row[12]),
                provider_response=provider_response,
                quote=quote,
            )


@router.get("/wallets/{wallet_id}/payouts", response_model=PayoutListResponse)
def list_wallet_payouts(
    wallet_id: UUID,
    response: Response,
    limit: int = Query(30, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
):
    response.headers["X-Nepxy-Payouts-Version"] = PAYOUTS_ROUTE_VERSION

    with get_conn() as conn:
        # Always reset transaction state in case the connection was previously aborted
        _rollback_quiet(conn)

        with conn.cursor() as cur:
            # ✅ ownership check without db_session actor
            _assert_wallet_owned_by_user(cur, conn, wallet_id, user.user_id)

            entry_schema, entry_table = _discover_entries_table(cur)
            entry_ref = f"{_qident(entry_schema)}.{_qident(entry_table)}"

            try:
                cur.execute(
                    f"""
                    SELECT
                      p.transaction_id,
                      p.provider,
                      p.phone_e164,
                      p.provider_ref,
                      p.status,
                      p.last_error,
                      p.retryable,
                      p.attempt_count,
                      p.amount_cents,
                      p.currency,
                      p.created_at,
                      p.updated_at,
                      p.provider_response
                    FROM app.mobile_money_payouts p
                    WHERE EXISTS (
                      SELECT 1
                      FROM {entry_ref} e
                      WHERE e.transaction_id = p.transaction_id
                        AND e.wallet_id = %s::uuid
                    )
                    ORDER BY p.created_at DESC, p.transaction_id DESC
                    LIMIT %s;
                    """,
                    (str(wallet_id), limit),
                )
                rows = cur.fetchall() or []
            except Exception as e:
                _rollback_quiet(conn)
                logger.exception("payouts query failed wallet=%s entries=%s", wallet_id, entry_ref)
                raise HTTPException(
                    status_code=500,
                    detail=f"PAYOUTS_QUERY_FAILED: {type(e).__name__}: {e} | entries={entry_schema}.{entry_table}",
                )

            payouts: List[PayoutItem] = []
            for r in rows:
                pr = r[12]
                if pr is not None and not isinstance(pr, dict):
                    pr = {"raw": pr}

                payouts.append(
                    PayoutItem(
                        transaction_id=UUID(str(r[0])),
                        provider=str(r[1]),
                        phone_e164=str(r[2]),
                        provider_ref=(str(r[3]) if r[3] else None),
                        status=str(r[4]),
                        last_error=(str(r[5]) if r[5] else None),
                        retryable=bool(r[6]),
                        attempt_count=int(r[7] or 0),
                        amount_cents=int(r[8] or 0),
                        currency=str(r[9] or ""),
                        created_at=str(r[10]),
                        updated_at=str(r[11]),
                        provider_response=pr,
                    )
                )

            return PayoutListResponse(wallet_id=wallet_id, payouts=payouts)
