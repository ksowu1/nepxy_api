from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.catalog import destinations as catalog_destinations
from app.catalog import enablement as catalog_enablement
from services import corridors as corridors
from tests.conftest import _auth_headers, AuthedUser


def test_payout_quote_returns_methods_and_providers_for_gh(client: TestClient):
    payload = {"destination_country": "GH", "amount_cents": 1000}
    r = client.post("/v1/quotes/payout", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["destination_country"] == "GH"
    assert data["currency"] == "GHS"
    assert "MOBILE_MONEY_PAYOUT" in data["available_methods"]
    providers = data["providers_per_method"].get("MOBILE_MONEY_PAYOUT") or []
    assert providers, "Expected providers for MOBILE_MONEY_PAYOUT"


def test_payout_quote_coming_soon_has_note(client: TestClient):
    payload = {"destination_country": "TG", "amount_cents": 1000}
    r = client.post("/v1/quotes/payout", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["destination_country"] == "TG"
    assert data["notes"] == "COMING_SOON"


def test_cash_out_with_destination_country_selects_provider(
    client: TestClient, user2: AuthedUser, funded_wallet2_xof: str
):
    provider_ref = f"dest-country-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 150,
        "destination_country": "GH",
        "provider_ref": provider_ref,
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), r.text
    tx_id = r.json().get("transaction_id")
    assert tx_id

    payout = client.get(f"/v1/payouts/{tx_id}", headers=_auth_headers(user2.token))
    assert payout.status_code == 200, payout.text
    payout_json = payout.json()
    assert payout_json.get("provider") == "MOMO"


def test_cash_out_autopicks_thunes_when_available(
    client: TestClient, user2: AuthedUser, funded_wallet2_xof: str, monkeypatch
):
    base = catalog_destinations.build_destination("GH")
    assert base, "Expected GH destination"
    providers = dict(base.get("providers_per_method") or {})
    providers[catalog_destinations.DELIVERY_METHOD_MOBILE_MONEY] = ["MOMO", "THUNES"]
    patched = dict(base)
    patched["providers_per_method"] = providers
    monkeypatch.setitem(catalog_destinations.DESTINATIONS, "GH", patched)
    monkeypatch.setitem(catalog_enablement.ENABLED_PROVIDERS_BY_COUNTRY, "GH", ["MOMO", "THUNES"])
    monkeypatch.setitem(corridors.ALLOWED_PAYOUT_PROVIDERS, "GH", {"MOMO", "THUNES"})

    provider_ref = f"dest-thunes-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 150,
        "destination_country": "GH",
        "provider_ref": provider_ref,
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), r.text
    tx_id = r.json().get("transaction_id")
    assert tx_id

    payout = client.get(f"/v1/payouts/{tx_id}", headers=_auth_headers(user2.token))
    assert payout.status_code == 200, payout.text
    payout_json = payout.json()
    assert payout_json.get("provider") == "THUNES"


def test_cash_out_picks_first_provider_when_thunes_missing(
    client: TestClient, user2: AuthedUser, funded_wallet2_xof: str, monkeypatch
):
    base = catalog_destinations.build_destination("GH")
    assert base, "Expected GH destination"
    providers = dict(base.get("providers_per_method") or {})
    providers[catalog_destinations.DELIVERY_METHOD_MOBILE_MONEY] = ["TMONEY", "MOMO"]
    patched = dict(base)
    patched["providers_per_method"] = providers
    monkeypatch.setitem(catalog_destinations.DESTINATIONS, "GH", patched)
    monkeypatch.setitem(catalog_enablement.ENABLED_PROVIDERS_BY_COUNTRY, "GH", ["TMONEY", "MOMO"])
    monkeypatch.setitem(corridors.ALLOWED_PAYOUT_PROVIDERS, "GH", {"TMONEY", "MOMO"})

    provider_ref = f"dest-first-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 150,
        "destination_country": "GH",
        "provider_ref": provider_ref,
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), r.text
    tx_id = r.json().get("transaction_id")
    assert tx_id

    payout = client.get(f"/v1/payouts/{tx_id}", headers=_auth_headers(user2.token))
    assert payout.status_code == 200, payout.text
    payout_json = payout.json()
    assert payout_json.get("provider") == "TMONEY"


def test_cash_out_rejects_provider_not_in_country_list(
    client: TestClient, user2: AuthedUser, funded_wallet2_xof: str, monkeypatch
):
    base = catalog_destinations.build_destination("GH")
    assert base, "Expected GH destination"
    providers = dict(base.get("providers_per_method") or {})
    providers[catalog_destinations.DELIVERY_METHOD_MOBILE_MONEY] = ["MOMO"]
    patched = dict(base)
    patched["providers_per_method"] = providers
    monkeypatch.setitem(catalog_destinations.DESTINATIONS, "GH", patched)
    monkeypatch.setitem(catalog_enablement.ENABLED_PROVIDERS_BY_COUNTRY, "GH", ["MOMO", "TMONEY"])
    monkeypatch.setitem(corridors.ALLOWED_PAYOUT_PROVIDERS, "GH", {"MOMO", "TMONEY"})

    provider_ref = f"dest-not-allowed-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 150,
        "destination_country": "GH",
        "provider_ref": provider_ref,
        "provider": "TMONEY",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "PROVIDER_NOT_AVAILABLE_FOR_COUNTRY"


def test_cash_out_destination_country_coming_soon_returns_400(
    client: TestClient, user2: AuthedUser, funded_wallet2_xof: str
):
    provider_ref = f"dest-coming-soon-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 150,
        "destination_country": "TG",
        "provider_ref": provider_ref,
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "DESTINATION_COMING_SOON"


def test_cash_out_without_destination_country_still_works(
    client: TestClient, user2: AuthedUser, funded_wallet2_xof: str
):
    provider_ref = f"dest-backcompat-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 150,
        "country": "GH",
        "provider_ref": provider_ref,
        "provider": "MOMO",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), r.text
