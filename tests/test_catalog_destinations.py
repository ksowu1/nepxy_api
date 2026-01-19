from app.catalog.countries import AFRICAN_COUNTRIES
def test_list_all_returns_africa(client):
    r = client.get("/v1/catalog/destinations")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["count"] == len(AFRICAN_COUNTRIES)
    results = payload["results"]
    assert results, "Expected destinations"
    codes = {entry["country_iso2"] for entry in results}
    assert set(AFRICAN_COUNTRIES) == codes


def test_filter_available_true(client):
    r = client.get("/v1/catalog/destinations?available=true")
    assert r.status_code == 200, r.text
    payload = r.json()
    results = payload["results"]
    assert results, "Expected available destinations"
    assert all(entry["status"] == "AVAILABLE" for entry in results)
    assert {"GH", "BJ"}.issubset({entry["country_iso2"] for entry in results})


def test_get_country_detail(client):
    r = client.get("/v1/catalog/destinations/GH")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["country_iso2"] == "GH"
    assert payload["default_currency"] == "GHS"
    assert payload["status"] == "AVAILABLE"


def test_filter_by_method(client):
    r = client.get("/v1/catalog/destinations?method=BANK")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["count"] == 0
    assert payload["results"] == []
