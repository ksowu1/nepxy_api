def test_catalog_payout_providers(client):
    r = client.get("/v1/catalog/payout-providers")
    assert r.status_code == 200, r.text
    payload = r.json()

    send_countries = payload.get("send_countries") or []
    assert "US" in send_countries

    receive = payload.get("receive_countries") or []
    countries = {item.get("country") for item in receive}
    assert "GH" in countries
    assert "BJ" in countries
    assert "TG" not in countries
