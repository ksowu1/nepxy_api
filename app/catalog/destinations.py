from __future__ import annotations

from app.catalog.countries import AFRICAN_COUNTRIES, COUNTRY_META

DELIVERY_METHOD_MOBILE_MONEY = "MOBILE_MONEY_PAYOUT"
DELIVERY_METHOD_WALLET = "NEPXY_WALLET"
DELIVERY_METHOD_BANK = "BANK"
DELIVERY_METHOD_CASH_PICKUP = "CASH_PICKUP"

DELIVERY_METHODS = [
    DELIVERY_METHOD_MOBILE_MONEY,
    DELIVERY_METHOD_WALLET,
    DELIVERY_METHOD_BANK,
    DELIVERY_METHOD_CASH_PICKUP,
]

STATUS_AVAILABLE = "AVAILABLE"
STATUS_COMING_SOON = "COMING_SOON"

AVAILABLE_COUNTRIES = {"GH", "BJ"}

PROVIDERS_BY_COUNTRY: dict[str, list[str]] = {
    "GH": ["MOMO"],
    "BJ": ["MOMO", "TMONEY", "FLOOZ"],
    "TG": ["TMONEY", "FLOOZ", "THUNES"],
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().upper()


def _country_status(country: str) -> str:
    return STATUS_AVAILABLE if country in AVAILABLE_COUNTRIES else STATUS_COMING_SOON


def _providers_for_country(country: str) -> list[str]:
    providers = PROVIDERS_BY_COUNTRY.get(country)
    if providers is not None:
        return list(providers)
    return ["THUNES"]


def _build_destination(country: str) -> dict[str, object] | None:
    meta = COUNTRY_META.get(country)
    if not meta:
        return None
    if meta.get("region") != "AFRICA":
        return None
    return {
        "country_iso2": country,
        "country_name": meta.get("name"),
        "default_currency": meta.get("currency_code"),
        "status": _country_status(country),
        "delivery_methods": [DELIVERY_METHOD_MOBILE_MONEY, DELIVERY_METHOD_WALLET],
        "providers_per_method": {
            DELIVERY_METHOD_MOBILE_MONEY: _providers_for_country(country),
            DELIVERY_METHOD_WALLET: [],
            DELIVERY_METHOD_BANK: [],
            DELIVERY_METHOD_CASH_PICKUP: [],
        },
    }


DESTINATIONS: dict[str, dict[str, object]] = {}
for code in AFRICAN_COUNTRIES:
    entry = _build_destination(code)
    if entry:
        DESTINATIONS[code] = entry


def build_destination(country: str) -> dict[str, object] | None:
    code = _normalize(country)
    return DESTINATIONS.get(code)


def list_destinations(
    country: str | None = None,
    available: bool | None = None,
    method: str | None = None,
) -> list[dict[str, object]]:
    method_norm = _normalize(method)
    if method and method_norm not in DELIVERY_METHODS:
        return []

    codes = list(DESTINATIONS.keys())
    if country:
        code = _normalize(country)
        codes = [code] if code in DESTINATIONS else []

    destinations = []
    for code in sorted(codes):
        entry = DESTINATIONS.get(code)
        if not entry:
            continue
        if available is True and entry["status"] != STATUS_AVAILABLE:
            continue
        if available is False and entry["status"] != STATUS_COMING_SOON:
            continue
        if method and method_norm not in entry["delivery_methods"]:
            continue
        destinations.append(entry)

    return destinations
