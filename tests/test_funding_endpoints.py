from __future__ import annotations

import pytest
from settings import settings


@pytest.fixture()
def auth_headers(user1):
    return {"Authorization": f"Bearer {user1.token}"}


@pytest.mark.parametrize(
    "path,flag_attr",
    [
        ("/v1/funding/ach", "FUNDING_ACH_ENABLED"),
        ("/v1/funding/card", "FUNDING_CARD_ENABLED"),
        ("/v1/funding/wire", "FUNDING_WIRE_ENABLED"),
    ],
)
def test_funding_endpoints_gated(client, auth_headers, monkeypatch, path, flag_attr):
    monkeypatch.setattr(settings, flag_attr, False, raising=False)
    body = {
        "wallet_id": "00000000-0000-0000-0000-000000000001",
        "amount_cents": 1000,
        "currency": "USD",
        "external_ref": "client-ref-1",
    }
    r = client.post(path, json=body, headers=auth_headers)
    assert r.status_code == 503
    detail = r.json().get("detail", {})
    assert detail.get("error") == "FEATURE_DISABLED"
    assert detail.get("feature") in {"ACH", "CARD", "WIRE"}


@pytest.mark.parametrize(
    "path,flag_attr",
    [
        ("/v1/funding/ach", "FUNDING_ACH_ENABLED"),
        ("/v1/funding/card", "FUNDING_CARD_ENABLED"),
        ("/v1/funding/wire", "FUNDING_WIRE_ENABLED"),
    ],
)
def test_funding_endpoints_not_implemented(client, auth_headers, monkeypatch, path, flag_attr):
    monkeypatch.setattr(settings, flag_attr, True, raising=False)
    body = {
        "wallet_id": "00000000-0000-0000-0000-000000000001",
        "amount_cents": 1000,
        "currency": "USD",
        "external_ref": "client-ref-2",
    }
    r = client.post(path, json=body, headers=auth_headers)
    assert r.status_code == 501
    detail = r.json().get("detail", {})
    assert detail.get("error") == "NOT_IMPLEMENTED"
    assert detail.get("feature") in {"ACH", "CARD", "WIRE"}
    assert detail.get("request_id")
