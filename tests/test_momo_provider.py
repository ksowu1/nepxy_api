from __future__ import annotations

import json

from app.providers.mobile_money.momo import MomoProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)
        self.reason = "OK"

    def json(self):
        return self._payload


def _set_env(monkeypatch):
    monkeypatch.setenv("MOMO_ENV", "sandbox")
    monkeypatch.setenv("MOMO_API_USER_ID", "user-123")
    monkeypatch.setenv("MOMO_API_KEY", "key-123")
    monkeypatch.setenv("MOMO_DISBURSE_SUB_KEY", "sub-123")


def test_momo_token_success(monkeypatch):
    _set_env(monkeypatch)

    def fake_post(url, headers=None, auth=None, json=None):
        assert url.endswith("/disbursement/token/")
        assert headers["Ocp-Apim-Subscription-Key"] == "sub-123"
        assert auth == ("user-123", "key-123")
        return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})

    monkeypatch.setattr("app.providers.mobile_money.momo.requests.post", fake_post)

    provider = MomoProvider()
    token = provider.get_token()
    assert token == "token-123"


def test_momo_transfer_created(monkeypatch):
    _set_env(monkeypatch)
    calls = {"token": 0, "transfer": 0}
    monkeypatch.setenv("MOMO_SANDBOX_CURRENCY", "EUR")

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            calls["token"] += 1
            return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            calls["transfer"] += 1
            assert headers["Authorization"] == "Bearer token-123"
            assert headers["X-Target-Environment"] == "sandbox"
            assert headers["Ocp-Apim-Subscription-Key"] == "sub-123"
            assert json["currency"] == "EUR"
            return _FakeResponse(202, {"status": "PENDING", "referenceId": "momo-ref-123"})
        raise AssertionError("unexpected url")

    monkeypatch.setattr("app.providers.mobile_money.momo.requests.post", fake_post)

    provider = MomoProvider()
    payout = {
        "amount_cents": 1234,
        "currency": "XOF",
        "phone_e164": "+233201234567",
        "provider_ref": "ref-123",
        "external_ref": "ext-123",
        "country": "GH",
    }
    result = provider.initiate_payout(payout)
    assert result.status == "SENT"
    assert result.provider_ref == "momo-ref-123"
    assert result.response["stage"] == "create"
    assert result.response["http_status"] == 202
    assert result.response["body"]["status"] == "PENDING"
    assert calls["token"] == 1
    assert calls["transfer"] == 1


def test_momo_create_invalid_currency_non_retryable(monkeypatch):
    _set_env(monkeypatch)

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            return _FakeResponse(400, {"code": "INVALID_CURRENCY"})
        raise AssertionError("unexpected url")

    monkeypatch.setattr("app.providers.mobile_money.momo.requests.post", fake_post)

    provider = MomoProvider()
    result = provider.create_transfer(
        amount="1.00",
        currency="EUR",
        external_id="ext-123",
        phone_e164="+233201234567",
        reference_id="ref-123",
        note="NepXy cash-out",
    )
    assert result.status == "FAILED"
    assert result.retryable is False
    assert result.error == "INVALID_CURRENCY"


def test_momo_sandbox_currency_override(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.setenv("MOMO_SANDBOX_CURRENCY", "EUR")

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            assert json["currency"] == "EUR"
            return _FakeResponse(202, {"status": "PENDING", "referenceId": "momo-ref-123"})
        raise AssertionError("unexpected url")

    monkeypatch.setattr("app.providers.mobile_money.momo.requests.post", fake_post)

    provider = MomoProvider()
    payout = {
        "amount_cents": 1234,
        "currency": "XOF",
        "phone_e164": "+233201234567",
        "provider_ref": "ref-123",
        "external_ref": "ext-123",
        "country": "GH",
    }
    result = provider.initiate_payout(payout)
    assert result.status == "SENT"


def test_momo_real_uses_payout_currency(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.setenv("MOMO_ENV", "real")
    monkeypatch.setenv("MOMO_SANDBOX_CURRENCY", "EUR")

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            assert json["currency"] == "GHS"
            return _FakeResponse(202, {"status": "PENDING", "referenceId": "momo-ref-123"})
        raise AssertionError("unexpected url")

    monkeypatch.setattr("app.providers.mobile_money.momo.requests.post", fake_post)

    provider = MomoProvider()
    payout = {
        "amount_cents": 1234,
        "currency": "GHS",
        "phone_e164": "+233201234567",
        "provider_ref": "ref-123",
        "external_ref": "ext-123",
        "country": "GH",
    }
    result = provider.initiate_payout(payout)
    assert result.status == "SENT"


def test_momo_status_successful_updates_payout(monkeypatch):
    _set_env(monkeypatch)

    def fake_post(url, headers=None, auth=None, json=None):
        return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})

    def fake_get(url, headers=None):
        assert url.endswith("/disbursement/v1_0/transfer/ref-123")
        return _FakeResponse(200, {"status": "SUCCESSFUL"})

    monkeypatch.setattr("app.providers.mobile_money.momo.requests.post", fake_post)
    monkeypatch.setattr("app.providers.mobile_money.momo.requests.get", fake_get)

    provider = MomoProvider()
    result = provider.get_status({"provider_ref": "ref-123"})
    assert result.status == "CONFIRMED"
    assert result.response["stage"] == "poll"
    assert result.response["http_status"] == 200
    assert result.response["body"]["status"] == "SUCCESSFUL"
