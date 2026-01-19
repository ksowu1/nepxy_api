from fastapi import APIRouter, HTTPException

from app.catalog.countries import (
    AFRICA,
    ALL_REGIONS,
    COUNTRY_META,
    countries_for_region,
    currency_for_country,
    is_supported_country,
)
from app.catalog.enablement import (
    DELIVERY_METHOD_FIELDS,
    all_known_providers,
    destination_status,
    provider_status,
)
from app.catalog.destinations import build_destination, list_destinations
from services.corridors import payout_provider_catalog

router = APIRouter(prefix="/v1/catalog", tags=["catalog"])


@router.get("/payout-providers")
def list_payout_providers():
    return payout_provider_catalog()


@router.get("/countries")
def list_countries(region: str):
    normalized = (region or "").strip().upper()
    if normalized not in ALL_REGIONS:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_REGION")

    countries = []
    for country in countries_for_region(normalized):
        meta = COUNTRY_META.get(country)
        if not meta:
            continue
        countries.append(
            {
                "country": country,
                "name": meta.get("name"),
                "currency": meta.get("currency_code"),
                "status": destination_status(country),
            }
        )

    return {"region": normalized, "countries": countries}


@router.get("/delivery-methods")
def list_delivery_methods(dest_country: str):
    if not is_supported_country(dest_country):
        raise HTTPException(status_code=400, detail="UNSUPPORTED_DEST_COUNTRY")

    methods = []
    for provider in all_known_providers():
        fields = [dict(field) for field in DELIVERY_METHOD_FIELDS]
        methods.append(
            {
                "type": "MOBILE_MONEY",
                "provider": provider,
                "label": provider,
                "fields_required": fields,
                "status": provider_status(dest_country, provider),
            }
        )

    return {
        "dest_country": dest_country.upper(),
        "currency": currency_for_country(dest_country),
        "methods": methods,
    }


@router.get("/destinations")
def list_destination_catalog(
    country: str | None = None,
    available: bool | None = None,
    method: str | None = None,
):
    results = list_destinations(country=country, available=available, method=method)
    return {"count": len(results), "results": results}


@router.get("/destinations/{country}")
def get_destination(country: str):
    destination = build_destination(country)
    if not destination:
        raise HTTPException(status_code=404, detail="DESTINATION_NOT_FOUND")
    return destination
