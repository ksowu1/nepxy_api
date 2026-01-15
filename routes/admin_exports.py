# routes/admin_exports.py
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Iterable

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from db import get_conn
from db_session import set_db_actor
from deps.admin import require_admin
from deps.auth import CurrentUser

router = APIRouter(prefix="/v1/admin/exports", tags=["admin-exports"])


def _csv_stream(headers: list[str], rows: Iterable[tuple]) -> Iterable[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


@router.get("/payouts.csv")
def export_payouts_csv(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    admin: CurrentUser = Depends(require_admin),
):
    headers = [
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

    sql = """
        SELECT
          p.transaction_id::text AS transaction_id,
          COALESCE(tx.created_at, p.created_at) AS created_at,
          tx.country::text AS country,
          p.provider,
          p.status,
          tx.amount_cents,
          (
            SELECT COALESCE(SUM(e.amount_cents), 0)
            FROM ledger.ledger_entries e
            WHERE e.transaction_id = p.transaction_id
              AND e.memo = 'Cashout fee'
          ) AS fee_cents,
          NULL::text AS fx_rate,
          p.phone_e164 AS receiver_phone,
          tx.external_ref,
          p.provider_ref
        FROM app.mobile_money_payouts p
        LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
        WHERE COALESCE(tx.created_at, p.created_at) >= %s::date
          AND COALESCE(tx.created_at, p.created_at) < (%s::date + interval '1 day')
        ORDER BY COALESCE(tx.created_at, p.created_at) ASC
    """

    def _rows():
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, admin.user_id)
                cur.execute(sql, (from_date, to_date))
                for row in cur:
                    yield row

    response = StreamingResponse(_csv_stream(headers, _rows()), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=payouts.csv"
    return response


@router.get("/ledger.csv")
def export_ledger_csv(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    admin: CurrentUser = Depends(require_admin),
):
    headers = [
        "entry_id",
        "created_at",
        "account",
        "debit",
        "credit",
        "wallet_id",
        "transaction_id",
        "memo",
    ]

    sql = """
        SELECT
          e.id::text AS entry_id,
          e.created_at,
          e.account_id::text AS account,
          CASE WHEN e.dc = 'DEBIT' THEN e.amount_cents ELSE 0 END AS debit,
          CASE WHEN e.dc = 'CREDIT' THEN e.amount_cents ELSE 0 END AS credit,
          CASE WHEN a.account_type = 'WALLET' THEN e.account_id::text ELSE NULL END AS wallet_id,
          e.transaction_id::text AS transaction_id,
          COALESCE(e.memo, '') AS memo
        FROM ledger.ledger_entries e
        JOIN ledger.ledger_accounts a ON a.id = e.account_id
        WHERE e.created_at >= %s::date
          AND e.created_at < (%s::date + interval '1 day')
        ORDER BY e.created_at ASC
    """

    def _rows():
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, admin.user_id)
                cur.execute(sql, (from_date, to_date))
                for row in cur:
                    yield row

    response = StreamingResponse(_csv_stream(headers, _rows()), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=ledger.csv"
    return response
