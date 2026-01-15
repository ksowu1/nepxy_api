import json
import uuid
import hmac
import hashlib
from datetime import datetime, timezone

from db import get_conn
from settings import settings


def _sign(body_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _insert_ledger_transaction(*, external_ref: str) -> uuid.UUID:
    tx_id = uuid.uuid4()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ledger.ledger_transactions (
              id, type, status, country, currency, amount_cents, description, idempotency_key, external_ref
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                tx_id,
                "CASH_OUT",
                "PENDING",
                "TG",
                "XOF",
                1000,
                "pytest thunes",
                f"pytest-{uuid.uuid4()}",
                external_ref,
            ),
        )
        conn.commit()
    return tx_id


def _insert_thunes_payout(*, status: str, provider_ref: str) -> uuid.UUID:
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
              %s, %s, NULL, NULL, %s, NULL,
              %s, %s
            )
            """,
            (
                payout_id,
                tx_id,
                "THUNES",
                "+22890009911",
                provider_ref,
                status,
                1000,
                "XOF",
                None,
                0,
                True,
                now,
                now,
            ),
        )
        conn.commit()

    return tx_id


def _insert_thunes_payout_with_external_ref(*, status: str, external_ref: str, provider_ref: str | None = None) -> uuid.UUID:
    payout_id = uuid.uuid4()
    tx_id = _insert_ledger_transaction(external_ref=external_ref)
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
              %s, %s, NULL, NULL, %s, NULL,
              %s, %s
            )
            """,
            (
                payout_id,
                tx_id,
                "THUNES",
                "+22890009911",
                provider_ref,
                status,
                1000,
                "XOF",
                None,
                0,
                True,
                now,
                now,
            ),
        )
        conn.commit()

    return tx_id


def test_thunes_webhook_updates_payout_and_logs_event(client, monkeypatch):
    monkeypatch.setenv("THUNES_WEBHOOK_SECRET", "dev_secret_thunes")
    provider_ref = f"thunes-{uuid.uuid4()}"
    _insert_thunes_payout(status="PENDING", provider_ref=provider_ref)

    body_obj = {"provider_ref": provider_ref, "status": "SUCCESS"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_thunes")

    r = client.post(
        "/v1/webhooks/thunes",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 200, r.text

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM app.mobile_money_payouts WHERE provider_ref = %s",
            (provider_ref,),
        )
        row = cur.fetchone()
        assert row and row[0] == "CONFIRMED"

        cur.execute(
            """
            SELECT provider, provider_ref, signature_valid
            FROM app.webhook_events
            WHERE provider = 'THUNES' AND provider_ref = %s
            ORDER BY received_at DESC
            LIMIT 1
            """,
            (provider_ref,),
        )
        row = cur.fetchone()
        assert row and row[0] == "THUNES"
        assert row[1] == provider_ref
        assert row[2] is True


def test_thunes_webhook_updates_by_external_ref(client, monkeypatch):
    monkeypatch.setenv("THUNES_WEBHOOK_SECRET", "dev_secret_thunes")
    external_ref = f"ext-{uuid.uuid4()}"
    _insert_thunes_payout_with_external_ref(status="PENDING", external_ref=external_ref, provider_ref=None)

    body_obj = {"external_ref": external_ref, "status": "SUCCESS"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_thunes")

    r = client.post(
        "/v1/webhooks/thunes",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 200, r.text

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.status
            FROM app.mobile_money_payouts p
            JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
            WHERE tx.external_ref = %s
            """,
            (external_ref,),
        )
        row = cur.fetchone()
        assert row and row[0] == "CONFIRMED"


def test_thunes_send_cashout_uses_external_ref(monkeypatch):
    from app.providers.mobile_money.thunes import ThunesProvider

    monkeypatch.setattr(settings, "MM_MODE", "sandbox")
    monkeypatch.setattr(settings, "THUNES_SANDBOX_API_ENDPOINT", "https://example.test")
    monkeypatch.setattr(settings, "THUNES_SANDBOX_API_KEY", "key")
    monkeypatch.setattr(settings, "THUNES_SANDBOX_API_SECRET", "secret")
    monkeypatch.setattr(settings, "THUNES_PAYER_ID_TG", "1234")
    monkeypatch.setattr(settings, "THUNES_SENDER_FIRSTNAME", "John")
    monkeypatch.setattr(settings, "THUNES_SENDER_LASTNAME", "Doe")
    monkeypatch.setattr(settings, "THUNES_SENDER_NATIONALITY_ISO3", "USA")
    monkeypatch.setattr(settings, "THUNES_SENDER_DOB", "1970-01-01")
    monkeypatch.setattr(settings, "THUNES_SENDER_COUNTRY_OF_BIRTH_ISO3", "USA")
    monkeypatch.setattr(settings, "THUNES_SENDER_GENDER", "MALE")
    monkeypatch.setattr(settings, "THUNES_SENDER_ADDRESS", "42 Main Street")
    monkeypatch.setattr(settings, "THUNES_SENDER_CITY", "New York")
    monkeypatch.setattr(settings, "THUNES_SENDER_POSTAL", "10001")
    monkeypatch.setattr(settings, "THUNES_SENDER_COUNTRY_ISO3", "USA")

    captured = {"quote": None}

    class FakeResp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data
            self.text = json.dumps(data)

        def json(self):
            return self._data

    def fake_post(url, json=None, headers=None, auth=None, timeout=None):
        if url.endswith("/quotations"):
            captured["quote"] = json
            return FakeResp(201, {"id": "quote-1"})
        if "/quotations/quote-1/transactions" in url:
            return FakeResp(201, {"id": "thunes-tx-123"})
        if url.endswith("/transactions/thunes-tx-123/confirm"):
            return FakeResp(202, {"status": "PENDING"})
        return FakeResp(500, {"error": "unexpected"})

    monkeypatch.setattr("app.providers.mobile_money.thunes.requests.post", fake_post)

    provider = ThunesProvider()
    payout = {
        "transaction_id": str(uuid.uuid4()),
        "external_ref": "ext-123",
        "provider_ref": None,
        "amount_cents": 1234,
        "currency": "XOF",
        "country": "TG",
        "phone_e164": "+22890009911",
    }
    res = provider.send_cashout(payout)
    assert res.status == "SENT"
    assert res.provider_ref == "thunes-tx-123"
    assert captured["quote"]["external_id"] == "ext-123"


def test_thunes_get_cashout_status_mapping(monkeypatch):
    from app.providers.mobile_money.thunes import ThunesProvider

    monkeypatch.setattr(settings, "MM_MODE", "sandbox")
    monkeypatch.setattr(settings, "THUNES_SANDBOX_API_ENDPOINT", "https://example.test")
    monkeypatch.setattr(settings, "THUNES_SANDBOX_API_KEY", "key")
    monkeypatch.setattr(settings, "THUNES_SANDBOX_API_SECRET", "secret")

    class FakeResp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data
            self.text = json.dumps(data)

        def json(self):
            return self._data

    def fake_get_completed(url, headers=None, auth=None, timeout=None):
        return FakeResp(200, {"status": "COMPLETED"})

    def fake_get_failed(url, headers=None, auth=None, timeout=None):
        return FakeResp(200, {"status": "FAILED"})

    def fake_get_pending(url, headers=None, auth=None, timeout=None):
        return FakeResp(200, {"status": "PENDING"})

    payout = {"provider_ref": "thunes-ref-1"}
    provider = ThunesProvider()

    monkeypatch.setattr("app.providers.mobile_money.thunes.requests.get", fake_get_completed)
    res = provider.get_cashout_status(payout)
    assert res.status == "CONFIRMED"
    assert res.provider_ref == "thunes-ref-1"

    monkeypatch.setattr("app.providers.mobile_money.thunes.requests.get", fake_get_failed)
    res = provider.get_cashout_status(payout)
    assert res.status == "FAILED"
    assert res.error == "FAILED"

    monkeypatch.setattr("app.providers.mobile_money.thunes.requests.get", fake_get_pending)
    res = provider.get_cashout_status(payout)
    assert res.status == "SENT"
