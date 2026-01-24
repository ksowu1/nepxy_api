import logging

from app.providers.mobile_money.thunes import ThunesProvider
from settings import settings


def test_thunes_headers_include_simulation_in_sandbox(monkeypatch, caplog):
    monkeypatch.setattr(settings, "MM_MODE", "sandbox", raising=False)
    monkeypatch.setattr(settings, "THUNES_USE_SIMULATION", True, raising=False)

    caplog.set_level(logging.INFO)
    provider = ThunesProvider()
    headers = provider._build_headers()

    assert headers.get("x-simulated-transaction") == "true"
    assert any(
        "thunes sandbox simulation headers enabled" in record.message for record in caplog.records
    )


def test_thunes_headers_no_simulation_in_real(monkeypatch, caplog):
    monkeypatch.setattr(settings, "MM_MODE", "real", raising=False)
    monkeypatch.setattr(settings, "THUNES_USE_SIMULATION", True, raising=False)

    caplog.set_level(logging.INFO)
    provider = ThunesProvider()
    headers = provider._build_headers()

    assert "x-simulated-transaction" not in headers
    assert not any(
        "thunes sandbox simulation headers enabled" in record.message for record in caplog.records
    )
