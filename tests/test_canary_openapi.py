from __future__ import annotations

import os
import sys


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import canary_smoke  # noqa: E402


def test_canary_openapi_validator_detects_missing_paths():
    openapi = {"paths": {"/v1/auth/login": {}}}
    missing, _ = canary_smoke._validate_openapi_paths(openapi, allow_bootstrap=False)
    assert "/v1/cash-in/mobile-money" in missing
    assert "/v1/webhooks/tmoney" in missing


def test_canary_bootstrap_preflight_handles_404(monkeypatch, capsys):
    class DummyResp:
        status_code = 404
        reason = "Not Found"

    def fake_request_raw(method, url, headers=None, json_body=None, data=None):
        return DummyResp()

    monkeypatch.setenv("CANARY_ALLOW_BOOTSTRAP", "1")
    monkeypatch.setattr(canary_smoke, "request_raw", fake_request_raw)

    assert canary_smoke.bootstrap_preflight("http://example.test", "secret") is True
    captured = capsys.readouterr()
    assert "Bootstrap endpoint not available; skipping." in captured.out


def test_canary_bootstrap_runs_only_when_enabled(monkeypatch):
    class DummyResp:
        def __init__(self, status_code, json_data=None, text="", reason=""):
            self.status_code = status_code
            self._json = json_data or {}
            self.text = text
            self.reason = reason

        def json(self):
            return self._json

    calls = {"bootstrap": 0, "login": 0}
    responses = [
        DummyResp(401, {"detail": "INVALID_CREDENTIALS"}, "unauthorized", "Unauthorized"),
        DummyResp(200, {"access_token": "ok"}),
    ]

    def fake_request_raw(method, url, headers=None, json_body=None, data=None):
        calls["login"] += 1
        return responses.pop(0)

    def fake_bootstrap(*_args, **_kwargs):
        calls["bootstrap"] += 1
        return {"mode": "staging-users", "info": {}}

    monkeypatch.setenv("CANARY_ALLOW_BOOTSTRAP", "1")
    monkeypatch.setattr(canary_smoke, "request_raw", fake_request_raw)
    monkeypatch.setattr(canary_smoke, "maybe_bootstrap_users", fake_bootstrap)

    token = canary_smoke.login_with_optional_bootstrap(
        "http://example.test",
        "user@example.com",
        "bad-pass",
        "secret",
        base_email="user@example.com",
        base_password="good-pass",
    )
    assert token == "ok"
    assert calls["bootstrap"] == 1

    calls["bootstrap"] = 0
    monkeypatch.delenv("CANARY_ALLOW_BOOTSTRAP", raising=False)
    responses[:] = [DummyResp(401, {"detail": "INVALID_CREDENTIALS"}, "unauthorized", "Unauthorized")]

    token = canary_smoke.login_with_optional_bootstrap(
        "http://example.test",
        "user@example.com",
        "bad-pass",
        "secret",
        base_email="user@example.com",
        base_password="good-pass",
    )
    assert token is None
    assert calls["bootstrap"] == 0
