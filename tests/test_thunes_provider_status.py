from __future__ import annotations

from app.providers.mobile_money.thunes import ThunesProvider


def test_thunes_status_mapping():
    provider = ThunesProvider()

    status, retryable, last_error = provider.map_thunes_status("COMPLETED")
    assert status == "CONFIRMED"
    assert retryable is False
    assert last_error is None

    status, retryable, last_error = provider.map_thunes_status("FAILED")
    assert status == "FAILED"
    assert retryable is False
    assert last_error == "FAILED"

    status, retryable, last_error = provider.map_thunes_status("PENDING")
    assert status == "SENT"
    assert retryable is True
    assert last_error is None
