from __future__ import annotations

from settings import Settings


def test_provider_flags_default_false_in_prod(monkeypatch):
    monkeypatch.delenv("TMONEY_ENABLED", raising=False)
    monkeypatch.delenv("FLOOZ_ENABLED", raising=False)
    monkeypatch.delenv("MOMO_ENABLED", raising=False)
    monkeypatch.delenv("THUNES_ENABLED", raising=False)
    s = Settings(_env_file=None, DATABASE_URL="postgresql://example")
    assert s.TMONEY_ENABLED is False
    assert s.FLOOZ_ENABLED is False
    assert s.MOMO_ENABLED is False
    assert s.THUNES_ENABLED is False


def test_provider_flags_true_only_when_explicit(monkeypatch):
    monkeypatch.setenv("TMONEY_ENABLED", "true")
    monkeypatch.delenv("FLOOZ_ENABLED", raising=False)
    monkeypatch.delenv("MOMO_ENABLED", raising=False)
    monkeypatch.setenv("THUNES_ENABLED", "false")
    s = Settings(_env_file=None, DATABASE_URL="postgresql://example")
    assert s.TMONEY_ENABLED is True
    assert s.FLOOZ_ENABLED is False
    assert s.MOMO_ENABLED is False
    assert s.THUNES_ENABLED is False
