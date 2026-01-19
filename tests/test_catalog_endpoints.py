def test_catalog_countries_includes_african_countries(client):
    r = client.get("/v1/catalog/countries?region=AFRICA")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["region"] == "AFRICA"
    assert payload["countries"], "Expected country data"
    codes = {entry["country"] for entry in payload["countries"]}
    assert "GH" in codes and "NG" in codes and "ZA" in codes
    gh = next(entry for entry in payload["countries"] if entry["country"] == "GH")
    assert gh["currency"] == "GHS"
    assert gh["status"] == "AVAILABLE"


def test_catalog_countries_europe_includes_france_and_coming_soon(client):
    r = client.get("/v1/catalog/countries?region=EUROPE")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["region"] == "EUROPE"
    codes = {entry["country"] for entry in payload["countries"]}
    assert "FR" in codes and "DE" in codes and "IT" in codes
    france = next(entry for entry in payload["countries"] if entry["country"] == "FR")
    assert france["currency"] == "EUR"
    assert france["status"] == "COMING_SOON"


def test_catalog_countries_north_america_includes_canada(client):
    r = client.get("/v1/catalog/countries?region=NORTH_AMERICA")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["region"] == "NORTH_AMERICA"
    canada = next(entry for entry in payload["countries"] if entry["country"] == "CA")
    assert canada["currency"] == "CAD"
    assert canada["status"] == "COMING_SOON"


def test_delivery_methods_gh_has_available_method(client):
    r = client.get("/v1/catalog/delivery-methods?dest_country=GH")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["dest_country"] == "GH"
    assert payload["currency"] == "GHS"
    assert payload["methods"], "Expected available methods"
    assert any(method["status"] == "AVAILABLE" for method in payload["methods"])


def test_delivery_methods_non_enabled_country_is_coming_soon(client):
    r = client.get("/v1/catalog/delivery-methods?dest_country=NG")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["dest_country"] == "NG"
    assert payload["currency"] == "NGN"
    assert payload["methods"], "Expected method list"
    assert all(method["status"] == "COMING_SOON" for method in payload["methods"])
