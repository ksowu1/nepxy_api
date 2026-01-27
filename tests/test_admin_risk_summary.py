from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import _auth_headers
from db import get_conn


def _insert_decline(user_id: str, reason: str, *, hours_ago: int = 0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app.risk_declines (id, user_id, reason, created_at)
                VALUES (%s::uuid, %s::uuid, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    str(user_id),
                    reason,
                    datetime.now(timezone.utc) - timedelta(hours=hours_ago),
                ),
            )
        conn.commit()


def test_risk_summary_admin_only(client: TestClient):
    r = client.get("/v1/admin/risk/summary")
    assert r.status_code in (401, 403), r.text


def test_risk_summary_counts(admin, client: TestClient, user1, user2):
    _insert_decline(user1.user_id, "LIMIT_DAILY")
    _insert_decline(user1.user_id, "LIMIT_MONTHLY")
    _insert_decline(user2.user_id, "VELOCITY")
    _insert_decline(user2.user_id, "CORRIDOR_BLOCKED")
    _insert_decline(user2.user_id, "VELOCITY")

    r = client.get(
        "/v1/admin/risk/summary?window_hours=24",
        headers=_auth_headers(admin.token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    by_reason = {row["reason"]: row["count"] for row in data.get("by_reason")}
    assert by_reason.get("LIMIT_DAILY") == 1
    assert by_reason.get("LIMIT_MONTHLY") == 1
    assert by_reason.get("VELOCITY") == 2
    assert by_reason.get("CORRIDOR_BLOCKED") == 1

    top_users = data.get("top_users") or []
    top = {row["user_id"]: row["count"] for row in top_users}
    assert top.get(str(user2.user_id)) == 3
    assert top.get(str(user1.user_id)) == 2


def test_risk_summary_window_filter(admin, client: TestClient, user1):
    _insert_decline(user1.user_id, "LIMIT_DAILY", hours_ago=30)
    _insert_decline(user1.user_id, "LIMIT_DAILY", hours_ago=2)

    r = client.get(
        "/v1/admin/risk/summary?window_hours=6",
        headers=_auth_headers(admin.token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    by_reason = {row["reason"]: row["count"] for row in data.get("by_reason")}
    assert by_reason.get("LIMIT_DAILY") == 1
