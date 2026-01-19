from __future__ import annotations

import json

from services.providers.momo import MomoProvider


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

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)

    provider = MomoProvider()
    token = provider.get_token()
    assert token == "token-123"


def test_momo_transfer_created(monkeypatch):
    _set_env(monkeypatch)
    calls = {"token": 0, "transfer": 0}

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            calls["token"] += 1
            return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            calls["transfer"] += 1
            assert headers["Authorization"] == "Bearer token-123"
            assert headers["X-Target-Environment"] == "sandbox"
            assert headers["Ocp-Apim-Subscription-Key"] == "sub-123"
            assert json["currency"] == "GHS"
            return _FakeResponse(202, {"status": "PENDING"})
        raise AssertionError("unexpected url")

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)

    provider = MomoProvider()
    payout = {
        "amount_cents": 1234,
        "currency": "GHS",
        "phone_e164": "+233201234567",
        "provider_ref": "ref-123",
        "external_ref": "ext-123",
    }
    result = provider.initiate_payout(payout)
    assert result.status == "SENT"
    assert result.provider_ref == "ref-123"
    assert result.response == {"status": "PENDING"}
    assert calls["token"] == 1
    assert calls["transfer"] == 1


def test_momo_status_successful_updates_payout(monkeypatch):
    _set_env(monkeypatch)

    def fake_post(url, headers=None, auth=None, json=None):
        return _FakeResponse(200, {"access_token": "token-123", "expires_in": 3600})

    def fake_get(url, headers=None):
        assert url.endswith("/disbursement/v1_0/transfer/ref-123")
        return _FakeResponse(200, {"status": "SUCCESSFUL"})

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)
    monkeypatch.setattr("services.providers.momo.requests.get", fake_get)

    provider = MomoProvider()
    result = provider.get_status({"provider_ref": "ref-123"})
    assert result.status == "CONFIRMED"
    assert result.response == {"status": "SUCCESSFUL"}
