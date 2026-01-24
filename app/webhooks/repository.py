


#app/webhooks/repository.py
from __future__ import annotations

from typing import Any
from psycopg2.extensions import connection as PGConn
from psycopg2.extras import Json


def insert_webhook_event(
    conn: PGConn,
    *,
    provider: str,
    path: str,
    request_id: str | None = None,
    headers: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    body_raw: str | None = None,
    signature: str | None = None,
    signature_valid: bool | None = None,
    signature_error: str | None = None,
    provider_ref: str | None = None,
    external_ref: str | None = None,
    status_raw: str | None = None,
    payout_transaction_id: str | None = None,
    payout_status_before: str | None = None,
    payout_status_after: str | None = None,
    update_applied: bool | None = None,
    ignored: bool | None = None,
    ignore_reason: str | None = None,
) -> str:
    """
    Insert a webhook event for audit/debugging.
    NOTE: caller commits.
    """
    h = headers or {}

    sql = """
    INSERT INTO webhook_events (
      provider, path, request_id,
      signature, signature_valid, signature_error,
      headers, body, body_raw,
      provider_ref, external_ref, status_raw,
      payout_transaction_id,
      payout_status_before, payout_status_after,
      update_applied,
      ignored, ignore_reason
    )
    VALUES (
      %(provider)s, %(path)s, %(request_id)s,
      %(signature)s, %(signature_valid)s, %(signature_error)s,
      %(headers)s, %(body)s, %(body_raw)s,
      %(provider_ref)s, %(external_ref)s, %(status_raw)s,
      %(payout_transaction_id)s,
      %(payout_status_before)s, %(payout_status_after)s,
      %(update_applied)s,
      %(ignored)s, %(ignore_reason)s
    )
    RETURNING id
    """

    params = {
        "provider": provider,
        "path": path,
        "request_id": request_id,
        "signature": signature,
        "signature_valid": signature_valid,
        "signature_error": signature_error,
        "headers": Json(h),
        "body": Json(body) if body is not None else None,
        "body_raw": body_raw,
        "provider_ref": provider_ref,
        "external_ref": external_ref,
        "status_raw": status_raw,
        "payout_transaction_id": payout_transaction_id,
        "payout_status_before": payout_status_before,
        "payout_status_after": payout_status_after,
        "update_applied": update_applied,
        "ignored": ignored,
        "ignore_reason": ignore_reason,
    }

    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        assert row and row[0], "insert_webhook_event: missing id"
        return str(row[0])



def insert_webhook_event(conn: PGConn, *, provider: str, path: str, request_id: str | None = None, headers: dict[str, Any] | None = None,
                         body: dict[str, Any] | None = None, body_raw: str | None = None,
                         signature: str | None = None, signature_valid: bool | None = None,
                         signature_error: str | None = None, provider_ref: str | None = None,
                         external_ref: str | None = None, status_raw: str | None = None,
                         payout_transaction_id: str | None = None, payout_status_before: str | None = None,
                         payout_status_after: str | None = None, update_applied: bool | None = None,
                         ignored: bool | None = None, ignore_reason: str | None = None) -> str:
    h = headers or {}

    sql = """
    INSERT INTO webhook_events (
      provider, path, request_id,
      signature, signature_valid, signature_error,
      headers, body, body_raw,
      provider_ref, external_ref, status_raw,
      payout_transaction_id,
      payout_status_before, payout_status_after,
      update_applied,
      ignored, ignore_reason
    )
    VALUES (
      %(provider)s, %(path)s, %(request_id)s,
      %(signature)s, %(signature_valid)s, %(signature_error)s,
      %(headers)s, %(body)s, %(body_raw)s,
      %(provider_ref)s, %(external_ref)s, %(status_raw)s,
      %(payout_transaction_id)s,
      %(payout_status_before)s, %(payout_status_after)s,
      %(update_applied)s,
      %(ignored)s, %(ignore_reason)s
    )
    RETURNING id
    """

    params = {
        "provider": provider,
        "path": path,
        "request_id": request_id,
        "signature": signature,
        "signature_valid": signature_valid,
        "signature_error": signature_error,
        "headers": Json(h),
        "body": Json(body) if body is not None else None,
        "body_raw": body_raw,
        "provider_ref": provider_ref,
        "external_ref": external_ref,
        "status_raw": status_raw,
        "payout_transaction_id": payout_transaction_id,
        "payout_status_before": payout_status_before,
        "payout_status_after": payout_status_after,
        "update_applied": update_applied,
        "ignored": ignored,
        "ignore_reason": ignore_reason,
    }

    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        assert row and row[0], "insert_webhook_event: missing id"
        return str(row[0])


def list_webhook_events(
    conn: PGConn,
    *,
    provider: str | None = None,
    provider_ref: str | None = None,
    external_ref: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 200))

    where = []
    params: dict[str, Any] = {"limit": limit}

    if provider:
        where.append("provider = %(provider)s")
        params["provider"] = provider
    if provider_ref:
        where.append("provider_ref = %(provider_ref)s")
        params["provider_ref"] = provider_ref
    if external_ref:
        where.append("external_ref = %(external_ref)s")
        params["external_ref"] = external_ref

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
    SELECT
      id, provider, path, request_id, received_at,
      signature, signature_valid, signature_error,
      provider_ref, external_ref, status_raw,
      payout_transaction_id,
      payout_status_before, payout_status_after,
      update_applied, ignored, ignore_reason
    FROM webhook_events
    {where_sql}
    ORDER BY received_at DESC
    LIMIT %(limit)s
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_webhook_event(conn: PGConn, *, event_id: str) -> dict[str, Any] | None:
    sql = """
    SELECT
      id, provider, path, request_id, received_at,
      signature, signature_valid, signature_error,
      headers, body, body_raw,
      provider_ref, external_ref, status_raw,
      payout_transaction_id,
      payout_status_before, payout_status_after,
      update_applied, ignored, ignore_reason
    FROM webhook_events
    WHERE id = %(id)s
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"id": event_id})
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
