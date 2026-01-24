from __future__ import annotations


def test_default_port_is_8001(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    from main import _resolve_port

    assert _resolve_port() == 8001
