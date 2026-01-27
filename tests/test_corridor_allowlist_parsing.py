from __future__ import annotations

from services.corridors import _parse_corridors


def test_parse_corridor_allowlist_colon():
    corridors = _parse_corridors("US:GH,US:BJ")
    assert ("US", "GH") in corridors
    assert ("US", "BJ") in corridors


def test_parse_corridor_allowlist_arrow():
    corridors = _parse_corridors("US->GH,US->BJ")
    assert ("US", "GH") in corridors
    assert ("US", "BJ") in corridors
