from app.catalog.enablement import DELIVERY_METHOD_FIELDS, all_known_providers
from services.corridors import ALLOWED_PAYOUT_PROVIDERS, CURRENCY_RULES


def test_delivery_methods_gh_has_methods(client):
    r = client.get("/v1/catalog/delivery-methods?dest_country=GH")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["dest_country"] == "GH"
    assert payload["methods"], "expected at least one delivery method"
    assert payload["currency"] == CURRENCY_RULES["GH"]["payout"]


def test_delivery_methods_unsupported_country_returns_400(client):
    r = client.get("/v1/catalog/delivery-methods?dest_country=ZZ")
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "UNSUPPORTED_DEST_COUNTRY"


def test_delivery_methods_match_corridor_config(client):
    dest_country = "GH"
    r = client.get(f"/v1/catalog/delivery-methods?dest_country={dest_country}")
    assert r.status_code == 200, r.text
    payload = r.json()

    expected_currency = CURRENCY_RULES.get(dest_country, {}).get("payout")
    assert payload["currency"] == expected_currency

    methods = {method["provider"]: method for method in payload["methods"]}
    expected_available = ALLOWED_PAYOUT_PROVIDERS.get(dest_country, set())

    for provider in expected_available:
        method = methods.get(provider)
        assert method, f"missing provider {provider}"
        assert method["status"] == "AVAILABLE"

    default_fields = [dict(field) for field in DELIVERY_METHOD_FIELDS]
    for provider in all_known_providers():
        method = methods.get(provider)
        assert method, f"missing provider {provider}"
        if provider not in expected_available:
            assert method["status"] == "COMING_SOON"
        assert method["type"] == "MOBILE_MONEY"
        assert method["fields_required"] == default_fields
