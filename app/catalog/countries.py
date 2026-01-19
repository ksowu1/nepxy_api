from __future__ import annotations

AFRICA = "AFRICA"
EUROPE = "EUROPE"
NORTH_AMERICA = "NORTH_AMERICA"

COUNTRY_META: dict[str, dict[str, str]] = {
    "AO": {"name": "Angola", "currency_code": "AOA", "region": AFRICA},
    "BF": {"name": "Burkina Faso", "currency_code": "XOF", "region": AFRICA},
    "BI": {"name": "Burundi", "currency_code": "BIF", "region": AFRICA},
    "BJ": {"name": "Benin", "currency_code": "XOF", "region": AFRICA},
    "BW": {"name": "Botswana", "currency_code": "BWP", "region": AFRICA},
    "CD": {"name": "Democratic Republic of the Congo", "currency_code": "CDF", "region": AFRICA},
    "CF": {"name": "Central African Republic", "currency_code": "XAF", "region": AFRICA},
    "CG": {"name": "Congo", "currency_code": "XAF", "region": AFRICA},
    "CI": {"name": "Cote d'Ivoire", "currency_code": "XOF", "region": AFRICA},
    "CM": {"name": "Cameroon", "currency_code": "XAF", "region": AFRICA},
    "CV": {"name": "Cabo Verde", "currency_code": "CVE", "region": AFRICA},
    "DJ": {"name": "Djibouti", "currency_code": "DJF", "region": AFRICA},
    "DZ": {"name": "Algeria", "currency_code": "DZD", "region": AFRICA},
    "EG": {"name": "Egypt", "currency_code": "EGP", "region": AFRICA},
    "ER": {"name": "Eritrea", "currency_code": "ERN", "region": AFRICA},
    "ET": {"name": "Ethiopia", "currency_code": "ETB", "region": AFRICA},
    "GA": {"name": "Gabon", "currency_code": "XAF", "region": AFRICA},
    "GM": {"name": "Gambia", "currency_code": "GMD", "region": AFRICA},
    "GH": {"name": "Ghana", "currency_code": "GHS", "region": AFRICA},
    "GN": {"name": "Guinea", "currency_code": "GNF", "region": AFRICA},
    "GQ": {"name": "Equatorial Guinea", "currency_code": "XAF", "region": AFRICA},
    "GW": {"name": "Guinea-Bissau", "currency_code": "XOF", "region": AFRICA},
    "KE": {"name": "Kenya", "currency_code": "KES", "region": AFRICA},
    "KM": {"name": "Comoros", "currency_code": "KMF", "region": AFRICA},
    "LS": {"name": "Lesotho", "currency_code": "LSL", "region": AFRICA},
    "LR": {"name": "Liberia", "currency_code": "LRD", "region": AFRICA},
    "LY": {"name": "Libya", "currency_code": "LYD", "region": AFRICA},
    "MA": {"name": "Morocco", "currency_code": "MAD", "region": AFRICA},
    "MG": {"name": "Madagascar", "currency_code": "MGA", "region": AFRICA},
    "ML": {"name": "Mali", "currency_code": "XOF", "region": AFRICA},
    "MR": {"name": "Mauritania", "currency_code": "MRU", "region": AFRICA},
    "MU": {"name": "Mauritius", "currency_code": "MUR", "region": AFRICA},
    "MW": {"name": "Malawi", "currency_code": "MWK", "region": AFRICA},
    "MZ": {"name": "Mozambique", "currency_code": "MZN", "region": AFRICA},
    "NA": {"name": "Namibia", "currency_code": "NAD", "region": AFRICA},
    "NE": {"name": "Niger", "currency_code": "XOF", "region": AFRICA},
    "NG": {"name": "Nigeria", "currency_code": "NGN", "region": AFRICA},
    "RW": {"name": "Rwanda", "currency_code": "RWF", "region": AFRICA},
    "SC": {"name": "Seychelles", "currency_code": "SCR", "region": AFRICA},
    "SD": {"name": "Sudan", "currency_code": "SDG", "region": AFRICA},
    "SN": {"name": "Senegal", "currency_code": "XOF", "region": AFRICA},
    "SL": {"name": "Sierra Leone", "currency_code": "SLL", "region": AFRICA},
    "SO": {"name": "Somalia", "currency_code": "SOS", "region": AFRICA},
    "SS": {"name": "South Sudan", "currency_code": "SSP", "region": AFRICA},
    "ST": {"name": "Sao Tome and Principe", "currency_code": "STN", "region": AFRICA},
    "SZ": {"name": "Eswatini", "currency_code": "SZL", "region": AFRICA},
    "TD": {"name": "Chad", "currency_code": "XAF", "region": AFRICA},
    "TG": {"name": "Togo", "currency_code": "XOF", "region": AFRICA},
    "TN": {"name": "Tunisia", "currency_code": "TND", "region": AFRICA},
    "TZ": {"name": "Tanzania", "currency_code": "TZS", "region": AFRICA},
    "UG": {"name": "Uganda", "currency_code": "UGX", "region": AFRICA},
    "ZA": {"name": "South Africa", "currency_code": "ZAR", "region": AFRICA},
    "ZM": {"name": "Zambia", "currency_code": "ZMW", "region": AFRICA},
    "ZW": {"name": "Zimbabwe", "currency_code": "ZWL", "region": AFRICA},
    "AL": {"name": "Albania", "currency_code": "ALL", "region": EUROPE},
    "AD": {"name": "Andorra", "currency_code": "EUR", "region": EUROPE},
    "AM": {"name": "Armenia", "currency_code": "AMD", "region": EUROPE},
    "AT": {"name": "Austria", "currency_code": "EUR", "region": EUROPE},
    "AZ": {"name": "Azerbaijan", "currency_code": "AZN", "region": EUROPE},
    "BA": {"name": "Bosnia and Herzegovina", "currency_code": "BAM", "region": EUROPE},
    "BE": {"name": "Belgium", "currency_code": "EUR", "region": EUROPE},
    "BG": {"name": "Bulgaria", "currency_code": "BGN", "region": EUROPE},
    "BY": {"name": "Belarus", "currency_code": "BYN", "region": EUROPE},
    "CH": {"name": "Switzerland", "currency_code": "CHF", "region": EUROPE},
    "CY": {"name": "Cyprus", "currency_code": "EUR", "region": EUROPE},
    "CZ": {"name": "Czech Republic", "currency_code": "CZK", "region": EUROPE},
    "DE": {"name": "Germany", "currency_code": "EUR", "region": EUROPE},
    "DK": {"name": "Denmark", "currency_code": "DKK", "region": EUROPE},
    "EE": {"name": "Estonia", "currency_code": "EUR", "region": EUROPE},
    "ES": {"name": "Spain", "currency_code": "EUR", "region": EUROPE},
    "FI": {"name": "Finland", "currency_code": "EUR", "region": EUROPE},
    "FR": {"name": "France", "currency_code": "EUR", "region": EUROPE},
    "GB": {"name": "United Kingdom", "currency_code": "GBP", "region": EUROPE},
    "GE": {"name": "Georgia", "currency_code": "GEL", "region": EUROPE},
    "GR": {"name": "Greece", "currency_code": "EUR", "region": EUROPE},
    "HR": {"name": "Croatia", "currency_code": "HRK", "region": EUROPE},
    "HU": {"name": "Hungary", "currency_code": "HUF", "region": EUROPE},
    "IE": {"name": "Ireland", "currency_code": "EUR", "region": EUROPE},
    "IS": {"name": "Iceland", "currency_code": "ISK", "region": EUROPE},
    "IT": {"name": "Italy", "currency_code": "EUR", "region": EUROPE},
    "KZ": {"name": "Kazakhstan", "currency_code": "KZT", "region": EUROPE},
    "LI": {"name": "Liechtenstein", "currency_code": "CHF", "region": EUROPE},
    "LT": {"name": "Lithuania", "currency_code": "EUR", "region": EUROPE},
    "LU": {"name": "Luxembourg", "currency_code": "EUR", "region": EUROPE},
    "LV": {"name": "Latvia", "currency_code": "EUR", "region": EUROPE},
    "MD": {"name": "Moldova", "currency_code": "MDL", "region": EUROPE},
    "ME": {"name": "Montenegro", "currency_code": "EUR", "region": EUROPE},
    "MK": {"name": "North Macedonia", "currency_code": "MKD", "region": EUROPE},
    "MT": {"name": "Malta", "currency_code": "EUR", "region": EUROPE},
    "NL": {"name": "Netherlands", "currency_code": "EUR", "region": EUROPE},
    "NO": {"name": "Norway", "currency_code": "NOK", "region": EUROPE},
    "PL": {"name": "Poland", "currency_code": "PLN", "region": EUROPE},
    "PT": {"name": "Portugal", "currency_code": "EUR", "region": EUROPE},
    "RO": {"name": "Romania", "currency_code": "RON", "region": EUROPE},
    "RS": {"name": "Serbia", "currency_code": "RSD", "region": EUROPE},
    "RU": {"name": "Russia", "currency_code": "RUB", "region": EUROPE},
    "SE": {"name": "Sweden", "currency_code": "SEK", "region": EUROPE},
    "SI": {"name": "Slovenia", "currency_code": "EUR", "region": EUROPE},
    "SK": {"name": "Slovakia", "currency_code": "EUR", "region": EUROPE},
    "SM": {"name": "San Marino", "currency_code": "EUR", "region": EUROPE},
    "TR": {"name": "Turkey", "currency_code": "TRY", "region": EUROPE},
    "UA": {"name": "Ukraine", "currency_code": "UAH", "region": EUROPE},
    "VA": {"name": "Vatican City", "currency_code": "EUR", "region": EUROPE},
    "XK": {"name": "Kosovo", "currency_code": "EUR", "region": EUROPE},
    "CA": {"name": "Canada", "currency_code": "CAD", "region": NORTH_AMERICA},
}


def _normalize_code(value: str | None) -> str:
    return (value or "").strip().upper()


REGION_COUNTRY_CODES: dict[str, list[str]] = {}
for code, meta in COUNTRY_META.items():
    region = _normalize_code(meta.get("region"))
    codes = REGION_COUNTRY_CODES.get(region)
    if codes is None:
        REGION_COUNTRY_CODES[region] = [code]
    else:
        codes.append(code)

for region, codes in list(REGION_COUNTRY_CODES.items()):
    REGION_COUNTRY_CODES[region] = sorted({code for code in codes})


ALL_REGIONS = sorted(REGION_COUNTRY_CODES.keys())
AFRICAN_COUNTRIES = REGION_COUNTRY_CODES.get(AFRICA, [])
EUROPEAN_COUNTRIES = REGION_COUNTRY_CODES.get(EUROPE, [])
NORTH_AMERICAN_COUNTRIES = REGION_COUNTRY_CODES.get(NORTH_AMERICA, [])


def countries_for_region(region: str | None) -> list[str]:
    return REGION_COUNTRY_CODES.get(_normalize_code(region), [])


def is_supported_country(code: str | None) -> bool:
    return _normalize_code(code) in COUNTRY_META


def currency_for_country(code: str | None) -> str | None:
    meta = COUNTRY_META.get(_normalize_code(code))
    if not meta:
        return None
    return meta.get("currency_code")


def name_for_country(code: str | None) -> str | None:
    meta = COUNTRY_META.get(_normalize_code(code))
    if not meta:
        return None
    return meta.get("name")
