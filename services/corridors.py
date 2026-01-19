from __future__ import annotations

from fastapi import HTTPException

from app.catalog.enablement import ENABLED_DESTINATIONS, ENABLED_PROVIDERS_BY_COUNTRY

ALLOWED_SEND_COUNTRIES: set[str] = {"US"}
ALLOWED_RECEIVE_COUNTRIES: set[str] = {country.upper() for country in ENABLED_DESTINATIONS}

ALLOWED_PAYOUT_PROVIDERS: dict[str, set[str]] = {
    country.upper(): {provider.upper() for provider in providers}
    for country, providers in ENABLED_PROVIDERS_BY_COUNTRY.items()
}

CURRENCY_RULES: dict[str, dict[str, str]] = {
    "GH": {"funding": "USD", "payout": "GHS"},
    "BJ": {"funding": "USD", "payout": "XOF"},
}

FIELDS_REQUIRED_BY_COUNTRY: dict[str, list[str]] = {
    "GH": ["phone_e164"],
    "BJ": ["phone_e164"],
}


def validate_cash_out_corridor(country: str, provider: str) -> None:
    recv_country = (country or "").upper()
    provider_code = (provider or "").upper()

    if recv_country not in ALLOWED_RECEIVE_COUNTRIES:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_CORRIDOR")

    allowed = ALLOWED_PAYOUT_PROVIDERS.get(recv_country, set())
    if provider_code not in allowed:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_PROVIDER")


def payout_provider_catalog() -> dict:
    send_countries = sorted(ALLOWED_SEND_COUNTRIES)
    receive_countries = []
    for country in sorted(ALLOWED_RECEIVE_COUNTRIES):
        providers = sorted(ALLOWED_PAYOUT_PROVIDERS.get(country, set()))
        payout_currency = CURRENCY_RULES.get(country, {}).get("payout")
        currencies = [payout_currency] if payout_currency else []
        fields_required = FIELDS_REQUIRED_BY_COUNTRY.get(country, ["phone_e164"])
        receive_countries.append(
            {
                "country": country,
                "providers": providers,
                "currencies": currencies,
                "fields_required": fields_required,
            }
        )
    return {
        "send_countries": send_countries,
        "receive_countries": receive_countries,
    }
