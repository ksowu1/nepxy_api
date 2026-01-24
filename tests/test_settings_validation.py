from __future__ import annotations

import pytest

from settings import settings, validate_env_settings


def test_validate_env_allows_dev_missing(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "dev", raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "JWT_SECRET", "dev-secret-change-me", raising=False)
    validate_env_settings()


def test_validate_env_staging_fails_on_missing(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "staging", raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://example", raising=False)
    monkeypatch.setattr(settings, "JWT_SECRET", "dev-secret-change-me", raising=False)
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", "TMONEY", raising=False)
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_SECRET", raising=False)
    monkeypatch.setattr(settings, "TMONEY_WEBHOOK_SECRET", "", raising=False)

    with pytest.raises(RuntimeError) as exc:
        validate_env_settings()

    message = str(exc.value)
    assert "JWT_SECRET" in message
    assert "STAGING_GATE_KEY" in message
    assert "BOOTSTRAP_ADMIN_SECRET" in message
    assert "TMONEY_WEBHOOK_SECRET" in message


def test_validate_env_prod_fails_on_missing(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "prod", raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "JWT_SECRET", "dev-secret-change-me", raising=False)

    with pytest.raises(RuntimeError) as exc:
        validate_env_settings()

    message = str(exc.value)
    assert "DATABASE_URL" in message
    assert "JWT_SECRET" in message
