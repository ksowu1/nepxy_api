from __future__ import annotations

from schemas import MobileMoneyProvider

ENABLED_DESTINATIONS: list[str] = ["GH", "BJ"]

ENABLED_PROVIDERS_BY_COUNTRY: dict[str, list[str]] = {
    "GH": ["MOMO"],
    "BJ": ["MOMO", "TMONEY", "FLOOZ"],
}

DESTINATION_COMING_SOON = "DESTINATION_COMING_SOON"
PROVIDER_DISABLED = "PROVIDER_DISABLED"
MISSING_PROVIDER_CONFIG = "MISSING_PROVIDER_CONFIG"

DELIVERY_METHOD_FIELDS: list[dict[str, str]] = [{"name": "phone_e164", "type": "string"}]


def _normalize(code: str | None) -> str:
    return (code or "").strip().upper()


def _enabled_providers_for(country: str) -> list[str]:
    return [p.upper() for p in ENABLED_PROVIDERS_BY_COUNTRY.get(country, [])]


def all_known_providers() -> list[str]:
    return [provider.value for provider in MobileMoneyProvider]


def is_destination_enabled(code: str | None) -> bool:
    return _normalize(code) in ENABLED_DESTINATIONS


def enabled_providers_for_country(code: str | None) -> list[str]:
    return _enabled_providers_for(_normalize(code))


def is_provider_enabled_for_country(code: str | None, provider: str | None) -> bool:
    return _normalize(provider) in enabled_providers_for_country(code)


def provider_status(code: str | None, provider: str | None) -> str:
    if is_destination_enabled(code) and is_provider_enabled_for_country(code, provider):
        return "AVAILABLE"
    return "COMING_SOON"


def destination_status(code: str | None) -> str:
    return "AVAILABLE" if is_destination_enabled(code) else "COMING_SOON"
