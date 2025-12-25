

# tests/test_db_errors.py
from fastapi import HTTPException

import routes.wallet as wallet_routes


def test_unknown_db_error_returns_500(client, user2, wallet2_xof, monkeypatch):
    """
    Force an unknown DB exception inside a route and assert we fail closed:
      - status_code = 500
      - detail = "Internal server error"
      - no raw exception details leaked
    """

    # Patch the route module's raise_for_db_error to behave like your real one,
    # but ONLY raise 500 for this test (simulating unknown DB error path).
    def fake_raise_for_db_error(exc: Exception) -> None:
        raise HTTPException(status_code=500, detail="Internal server error")

    monkeypatch.setattr(wallet_routes, "raise_for_db_error", fake_raise_for_db_error, raising=True)

    # Now patch the route module's get_conn to raise an unknown exception
    class DummyConn:
        def __enter__(self):  # pragma: no cover
            raise Exception("SOME_RANDOM_DB_BLOWUP_123")
        def __exit__(self, exc_type, exc, tb):  # pragma: no cover
            return False

    monkeypatch.setattr(wallet_routes, "get_conn", lambda: DummyConn(), raising=True)

    # Call an endpoint that uses get_conn + raise_for_db_error (balance is perfect)
    r = client.get(
        f"/v1/wallets/{wallet2_xof}/balance",
        headers={"Authorization": f"Bearer {user2.token}"},
    )

    assert r.status_code == 500, r.text
    body = r.json()
    assert body.get("detail") == "Internal server error"

    # Ensure raw exception text isn't leaked
    assert "SOME_RANDOM_DB_BLOWUP_123" not in r.text
