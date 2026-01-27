from __future__ import annotations

from fastapi import HTTPException

from app.catalog.enablement import ENABLED_DESTINATIONS, ENABLED_PROVIDERS_BY_COUNTRY
from settings import settings

def _parse_corridors(raw: str | None) -> set[tuple[str, str]]:
    raw_value = raw or ""
    items = [i.strip().upper() for i in raw_value.split(",") if i.strip()]
    corridors: set[tuple[str, str]] = set()
    for item in items:
        if "->" in item:
            send, recv = item.split("->", 1)
        elif ":" in item:
            send, recv = item.split(":", 1)
        else:
            continue
        send = send.strip().upper()
        recv = recv.strip().upper()
        if send and recv:
            corridors.add((send, recv))
    return corridors


def _allowed_corridors() -> set[tuple[str, str]]:
    raw = (getattr(settings, "CORRIDOR_ALLOWLIST", "") or "").strip()
    if not raw:
        raw = getattr(settings, "ALLOWED_PAYOUT_CORRIDORS", "") or ""
    corridors = _parse_corridors(raw)
    if corridors:
        return corridors
    return {("US", country.upper()) for country in ENABLED_DESTINATIONS}


def _allowed_send_countries() -> set[str]:
    return {c[0] for c in _allowed_corridors()}


def _allowed_receive_countries() -> set[str]:
    return {c[1] for c in _allowed_corridors()}

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


def validate_cash_out_corridor(country: str, provider: str, *, send_country: str = "US") -> None:
    recv_country = (country or "").upper()
    provider_code = (provider or "").upper()
    send_country = (send_country or "").upper()

    corridors = _allowed_corridors()
    if (send_country, recv_country) not in corridors:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_CORRIDOR")

    allowed = ALLOWED_PAYOUT_PROVIDERS.get(recv_country, set())
    if provider_code not in allowed:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_PROVIDER")


def payout_provider_catalog() -> dict:
    send_countries = sorted(_allowed_send_countries())
    receive_countries = []
    for country in sorted(_allowed_receive_countries()):
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
