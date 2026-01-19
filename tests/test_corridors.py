import uuid

from app.catalog.enablement import MISSING_PROVIDER_CONFIG, PROVIDER_DISABLED
from tests.conftest import _auth_headers


def test_cash_out_gh_allowed_provider(client, user2, funded_wallet2_xof):
    idem = f"pytest-gh-cashout-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "country": "GH",
        "provider_ref": f"gh-ref-{uuid.uuid4()}",
        "provider": "MOMO",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 200, r.text


def test_cash_out_unsupported_country_fails(client, user2, funded_wallet2_xof):
    idem = f"pytest-unsupported-country-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "country": "TG",
        "provider_ref": f"tg-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "DESTINATION_COMING_SOON"


def test_cash_out_unsupported_provider_fails(client, user2, funded_wallet2_xof):
    idem = f"pytest-unsupported-provider-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "country": "GH",
        "provider_ref": f"gh-bad-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == PROVIDER_DISABLED


def test_cash_out_missing_provider_config_returns_503(
    client, user2, funded_wallet2_xof, monkeypatch
):
    monkeypatch.setattr("routes.payments.get_provider", lambda name: None)
    idem = f"pytest-missing-config-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "country": "GH",
        "provider_ref": f"gh-missing-ref-{uuid.uuid4()}",
        "provider": "MOMO",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 503, r.text
    assert r.json().get("detail") == MISSING_PROVIDER_CONFIG
