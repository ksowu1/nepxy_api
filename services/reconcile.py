from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from psycopg2.extras import RealDictCursor

from db import get_conn
from app.providers.base import ProviderResult
from app.providers.mobile_money.factory import get_provider
from app.providers.mobile_money.config import mm_mode


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _adapt_json(value: Any):
    try:
        from psycopg2.extras import Json as Psycopg2Json
        return Psycopg2Json(value)
    except Exception:
        return json.dumps(value)


def _ensure_reports_table(cur) -> None:
    cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app.reconcile_reports (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          run_at timestamptz NOT NULL DEFAULT now(),
          summary jsonb NOT NULL,
          items jsonb NOT NULL
        );
        """
    )


def _normalize_provider_result(result: Any) -> ProviderResult:
    if isinstance(result, ProviderResult):
        return result
    status = "FAILED"
    provider_ref = getattr(result, "provider_ref", None) or getattr(result, "provider_tx_id", None)
    ok = getattr(result, "ok", None)
    if ok is True:
        status = "CONFIRMED"
    elif ok is False:
        status = "FAILED"
    return ProviderResult(
        status=status,
        provider_ref=provider_ref,
        response=getattr(result, "response", None),
        error=getattr(result, "error", None),
        retryable=getattr(result, "retryable", None),
    )


def _deterministic_provider_status(payout: dict[str, Any]) -> ProviderResult:
    provider_ref = (payout.get("provider_ref") or "").lower()
    if "confirm" in provider_ref:
        return ProviderResult(status="CONFIRMED", provider_ref=payout.get("provider_ref"))
    if "fail" in provider_ref:
        return ProviderResult(status="FAILED", provider_ref=payout.get("provider_ref"))
    return ProviderResult(status="SENT", provider_ref=payout.get("provider_ref"))


def _get_provider_status(payout: dict[str, Any]) -> ProviderResult:
    mode = (mm_mode() or "sandbox").strip().lower()
    if mode == "sandbox":
        return _deterministic_provider_status(payout)

    provider_name = (payout.get("provider") or "").strip().upper()
    provider = get_provider(provider_name) if provider_name else None
    if provider is None:
        return _deterministic_provider_status(payout)

    try:
        res = provider.get_cashout_status(payout)
    except Exception as exc:
        return ProviderResult(status="SENT", provider_ref=payout.get("provider_ref"), error=str(exc), retryable=True)

    return _normalize_provider_result(res)


def _fetch_ledger_entry_presence(cur, tx_ids: Iterable[str]) -> dict[str, bool]:
    ids = list(tx_ids)
    if not ids:
        return {}
    cur.execute(
        """
        SELECT transaction_id::text AS transaction_id, COUNT(*)::int AS entry_count
        FROM ledger.ledger_entries
        WHERE transaction_id = ANY(%s::uuid[])
        GROUP BY transaction_id
        """,
        (ids,),
    )
    rows = cur.fetchall()
    return {row["transaction_id"]: row["entry_count"] > 0 for row in rows}


def run_reconcile(*, stale_minutes: int = 30, lookback_minutes: int = 240) -> dict[str, Any]:
    run_at = _utcnow()
    stale_after = run_at - timedelta(minutes=stale_minutes)
    lookback_after = run_at - timedelta(minutes=lookback_minutes)

    items: list[dict[str, Any]] = []
    summary = {
        "status_mismatch": 0,
        "confirmed_missing_ledger": 0,
        "ledger_missing_payout": 0,
        "stale_checked": 0,
        "confirmed_checked": 0,
        "ledger_checked": 0,
    }

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _ensure_reports_table(cur)

            if stale_minutes <= 0:
                cur.execute(
                    """
                    SELECT
                      p.id::text AS payout_id,
                      p.transaction_id::text AS transaction_id,
                      p.status,
                      p.provider,
                      p.provider_ref,
                      p.updated_at,
                      tx.amount_cents,
                      tx.currency,
                      tx.external_ref
                    FROM app.mobile_money_payouts p
                    LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
                    WHERE p.status IN ('SENT', 'PENDING')
                    """,
                )
            else:
                cur.execute(
                    """
                    SELECT
                      p.id::text AS payout_id,
                      p.transaction_id::text AS transaction_id,
                      p.status,
                      p.provider,
                      p.provider_ref,
                      p.updated_at,
                      tx.amount_cents,
                      tx.currency,
                      tx.external_ref
                    FROM app.mobile_money_payouts p
                    LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
                    WHERE p.status IN ('SENT', 'PENDING')
                      AND p.updated_at <= (now() - (%s || ' minutes')::interval)
                    """,
                    (stale_minutes,),
                )
            stale_rows = cur.fetchall()
            summary["stale_checked"] = len(stale_rows)

            for payout in stale_rows:
                provider_result = _get_provider_status(payout)
                provider_status = provider_result.status
                if provider_status != payout["status"]:
                    summary["status_mismatch"] += 1
                    items.append(
                        {
                            "category": "status_mismatch",
                            "payout_id": payout["payout_id"],
                            "transaction_id": payout["transaction_id"],
                            "payout_status": payout["status"],
                            "provider_status": provider_status,
                            "provider": payout.get("provider"),
                            "provider_ref": payout.get("provider_ref"),
                        }
                    )

            cur.execute(
                """
                SELECT p.transaction_id::text AS transaction_id, p.id::text AS payout_id
                FROM app.mobile_money_payouts p
                WHERE p.status = 'CONFIRMED'
                  AND p.updated_at >= (now() - (%s || ' minutes')::interval)
                """,
                (lookback_minutes,),
            )
            confirmed_rows = cur.fetchall()
            summary["confirmed_checked"] = len(confirmed_rows)
            confirmed_tx_ids = [row["transaction_id"] for row in confirmed_rows]
            ledger_presence = _fetch_ledger_entry_presence(cur, confirmed_tx_ids)

            for row in confirmed_rows:
                if not ledger_presence.get(row["transaction_id"], False):
                    summary["confirmed_missing_ledger"] += 1
                    items.append(
                        {
                            "category": "confirmed_missing_ledger",
                            "payout_id": row["payout_id"],
                            "transaction_id": row["transaction_id"],
                        }
                    )

            cur.execute(
                """
                SELECT t.id::text AS transaction_id, t.amount_cents, t.currency, t.created_at, t.type
                FROM ledger.ledger_transactions t
                WHERE t.created_at >= (now() - (%s || ' minutes')::interval)
                  AND t.type ILIKE 'CASH_OUT%%'
                  AND EXISTS (
                    SELECT 1 FROM ledger.ledger_entries e
                    WHERE e.transaction_id = t.id AND e.dc = 'DEBIT'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM app.mobile_money_payouts p WHERE p.transaction_id = t.id
                  )
                """,
                (lookback_minutes,),
            )
            ledger_rows = cur.fetchall()
            summary["ledger_checked"] = len(ledger_rows)
            for row in ledger_rows:
                summary["ledger_missing_payout"] += 1
                items.append(
                    {
                        "category": "ledger_missing_payout",
                        "transaction_id": row["transaction_id"],
                        "amount_cents": row["amount_cents"],
                        "currency": row["currency"],
                        "ledger_type": row["type"],
                    }
                )

            cur.execute(
                """
                INSERT INTO app.reconcile_reports (summary, items)
                VALUES (%s::jsonb, %s::jsonb)
                RETURNING id::text
                """,
                (_adapt_json(summary), _adapt_json(items)),
            )
            report_id = cur.fetchone()["id"]
            conn.commit()

    return {"id": report_id, "run_at": run_at.isoformat(), "summary": summary, "items": items}
