from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import routes.webhooks as webhooks
from main import create_app
from settings import settings, validate_env_settings
from db import get_conn
from app.workers import payout_worker


class _DummyConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        return None


@pytest.mark.parametrize(
    "provider,flag_attr",
    [
        ("TMONEY", "TMONEY_ENABLED"),
        ("FLOOZ", "FLOOZ_ENABLED"),
        ("MOMO", "MOMO_ENABLED"),
        ("THUNES", "THUNES_ENABLED"),
    ],
)
def test_validate_env_allows_missing_provider_when_disabled(monkeypatch, provider, flag_attr):
    monkeypatch.setattr(settings, "ENV", "prod", raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://example", raising=False)
    monkeypatch.setattr(settings, "JWT_SECRET", "a" * 32, raising=False)
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", provider, raising=False)
    monkeypatch.setattr(settings, flag_attr, False, raising=False)

    if provider == "TMONEY":
        monkeypatch.setattr(settings, "TMONEY_WEBHOOK_SECRET", "", raising=False)
    elif provider == "FLOOZ":
        monkeypatch.setattr(settings, "FLOOZ_WEBHOOK_SECRET", "", raising=False)
    elif provider == "MOMO":
        monkeypatch.setattr(settings, "MOMO_WEBHOOK_SECRET", "", raising=False)
    elif provider == "THUNES":
        monkeypatch.setattr(settings, "THUNES_WEBHOOK_SECRET", "", raising=False)
        monkeypatch.setattr(settings, "THUNES_PAYER_ID_GH", "", raising=False)
        monkeypatch.setattr(settings, "THUNES_REAL_API_ENDPOINT", "", raising=False)
        monkeypatch.setattr(settings, "THUNES_REAL_API_KEY", "", raising=False)
        monkeypatch.setattr(settings, "THUNES_REAL_API_SECRET", "", raising=False)

    validate_env_settings()


@pytest.mark.parametrize(
    "provider,flag_attr,path",
    [
        ("TMONEY", "TMONEY_ENABLED", "/v1/webhooks/tmoney"),
        ("FLOOZ", "FLOOZ_ENABLED", "/v1/webhooks/flooz"),
        ("MOMO", "MOMO_ENABLED", "/v1/webhooks/momo"),
        ("THUNES", "THUNES_ENABLED", "/v1/webhooks/thunes"),
    ],
)
def test_webhook_disabled_provider_returns_503(monkeypatch, provider, flag_attr, path):
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", provider, raising=False)
    monkeypatch.setattr(settings, flag_attr, False, raising=False)
    monkeypatch.setattr(webhooks, "get_conn", lambda: _DummyConn())
    captured = {}

    def _fake_log(conn, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(webhooks, "_log_both_tables", _fake_log)
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post(path, json={"external_ref": "ext-1", "status": "SUCCESS"})
    assert r.status_code == 503
    body = r.json()
    assert body.get("detail", {}).get("error") == "PROVIDER_DISABLED"
    assert captured.get("ignore_reason") == "PROVIDER_DISABLED"
    assert captured.get("provider") == provider


def _insert_payout(*, provider: str, status: str = "PENDING") -> uuid.UUID:
    payout_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app.mobile_money_payouts (
              id, transaction_id, provider, phone_e164, provider_ref,
              status, amount_cents, currency,
              last_error, attempt_count, last_attempt_at, next_retry_at, retryable, provider_response,
              created_at, updated_at
            )
            VALUES (
              %s, %s, %s, %s, %s,
              %s, %s, %s,
              NULL, 0, NULL, NULL, TRUE, NULL,
              %s, %s
            )
            """,
            (
                payout_id,
                tx_id,
                provider,
                "+22890000000",
                None,
                status,
                1000,
                "XOF",
                now,
                now,
            ),
        )
        conn.commit()

    return payout_id


def _get_status(payout_id: uuid.UUID) -> tuple[str, int, str | None]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, attempt_count, last_error
            FROM app.mobile_money_payouts
            WHERE id = %s
            """,
            (payout_id,),
        )
        row = cur.fetchone()
        assert row is not None
        return row[0], row[1], row[2]


@pytest.mark.parametrize(
    "provider,flag_attr",
    [
        ("TMONEY", "TMONEY_ENABLED"),
        ("FLOOZ", "FLOOZ_ENABLED"),
        ("MOMO", "MOMO_ENABLED"),
        ("THUNES", "THUNES_ENABLED"),
    ],
)
def test_worker_skips_disabled_provider(monkeypatch, provider, flag_attr):
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", provider, raising=False)
    monkeypatch.setattr(settings, flag_attr, False, raising=False)

    payout_id = _insert_payout(provider=provider, status="PENDING")

    for _ in range(3):
        payout_worker.process_once(batch_size=500, stale_seconds=0)
        status, attempts, last_error = _get_status(payout_id)
        if status == "FAILED":
            break

    assert status == "FAILED"
    assert attempts == 0
    assert last_error == "PROVIDER_DISABLED"
