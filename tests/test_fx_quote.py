from fastapi.testclient import TestClient


def test_fx_quote_usd_ghs(client: TestClient):
    r = client.get("/v1/fx/quote?from=USD&to=GHS&amount=100")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["from_currency"] == "USD"
    assert data["to_currency"] == "GHS"
    assert data["rate"] > 0
    assert data["inverse_rate"] > 0
    assert data["amount"] == 100.0
    assert data["converted_amount"] > 0
    assert data["updated_at"]
    assert data["source"]


def test_fx_quote_usd_xof(client: TestClient):
    r = client.get("/v1/fx/quote?from=USD&to=XOF&amount=50")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["from_currency"] == "USD"
    assert data["to_currency"] == "XOF"
    assert data["rate"] > 0
    assert data["inverse_rate"] > 0


def test_fx_quote_unsupported_pair(client: TestClient):
    r = client.get("/v1/fx/quote?from=USD&to=EUR&amount=10")
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "UNSUPPORTED_FX_PAIR"
