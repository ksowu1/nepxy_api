from __future__ import annotations

import pytest

from settings import settings


def test_provider_readiness_admin_only(client):
    r = client.get("/v1/admin/provider-readiness")
    assert r.status_code in (401, 403), r.text


def test_provider_readiness_missing_keys(monkeypatch, admin, client):
    monkeypatch.setattr(settings, "MM_MODE", "sandbox", raising=False)
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", "TMONEY,FLOOZ", raising=False)
    monkeypatch.setattr(settings, "TMONEY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "FLOOZ_ENABLED", False, raising=False)

    monkeypatch.setattr(settings, "TMONEY_WEBHOOK_SECRET", "", raising=False)
    monkeypatch.setattr(settings, "TMONEY_SANDBOX_API_KEY", "", raising=False)
    monkeypatch.setattr(settings, "TMONEY_SANDBOX_CASHOUT_URL", "", raising=False)

    r = client.get(
        "/v1/admin/provider-readiness",
        headers={"Authorization": f"Bearer {admin.token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    tmoney = data["providers"]["TMONEY"]
    flooz = data["providers"]["FLOOZ"]

    assert tmoney["enabled"] is True
    assert "TMONEY_WEBHOOK_SECRET" in tmoney["missing"]
    assert "TMONEY_SANDBOX_API_KEY" in tmoney["missing"]
    assert "TMONEY_SANDBOX_CASHOUT_URL" in tmoney["missing"]

    assert flooz["enabled"] is False
    assert flooz["missing"] == []


def test_provider_readiness_no_missing_when_configured(monkeypatch, admin, client):
    monkeypatch.setattr(settings, "MM_MODE", "sandbox", raising=False)
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", "TMONEY", raising=False)
    monkeypatch.setattr(settings, "TMONEY_ENABLED", True, raising=False)

    monkeypatch.setattr(settings, "TMONEY_WEBHOOK_SECRET", "tmoney-secret", raising=False)
    monkeypatch.setattr(settings, "TMONEY_SANDBOX_API_KEY", "key", raising=False)
    monkeypatch.setattr(settings, "TMONEY_SANDBOX_CASHOUT_URL", "https://sandbox.tmoney/cashout", raising=False)

    r = client.get(
        "/v1/admin/provider-readiness",
        headers={"Authorization": f"Bearer {admin.token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    tmoney = data["providers"]["TMONEY"]
    assert tmoney["enabled"] is True
    assert tmoney["missing"] == []
