from __future__ import annotations

import pytest
from fastapi import HTTPException

from settings import settings
from services.corridors import validate_cash_out_corridor


def test_corridor_allowlist_blocks_unlisted(monkeypatch):
    monkeypatch.setattr(settings, "CORRIDOR_ALLOWLIST", "US:GH", raising=False)
    with pytest.raises(HTTPException) as exc:
        validate_cash_out_corridor("BJ", "TMONEY")
    assert exc.value.detail == "UNSUPPORTED_CORRIDOR"


def test_corridor_allowlist_allows_listed(monkeypatch):
    monkeypatch.setattr(settings, "CORRIDOR_ALLOWLIST", "US:BJ", raising=False)
    validate_cash_out_corridor("BJ", "TMONEY")
