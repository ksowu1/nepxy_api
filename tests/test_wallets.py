

# tests/test_wallets.py
import uuid


def _wallets_from_response(data):
    # Support either {"wallets":[...]} or [...] formats
    if isinstance(data, dict) and "wallets" in data:
        return data["wallets"]
    if isinstance(data, list):
        return data
    return []


def test_list_wallets_user2(client, user2):
    r = client.get("/v1/wallets", headers={"Authorization": f"Bearer {user2.token}"})
    assert r.status_code == 200, r.text
    wallets = _wallets_from_response(r.json())
    assert isinstance(wallets, list)
    assert len(wallets) >= 1


def test_balance_own_wallet_200(client, user2, wallet2_xof):
    r = client.get(
        f"/v1/wallets/{wallet2_xof}/balance",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["wallet_id"] == wallet2_xof
    assert isinstance(data["balance_cents"], int)


def test_balance_other_users_wallet_forbidden(client, user2, wallet1_xof):
    r = client.get(
        f"/v1/wallets/{wallet1_xof}/balance",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_balance_fake_wallet_404(client, user2):
    fake_wallet = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
    r = client.get(
        f"/v1/wallets/{fake_wallet}/balance",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_transactions_pagination_cursor_stable(client, user2, wallet2_xof):
    # Page 1
    r1 = client.get(
        f"/v1/wallets/{wallet2_xof}/transactions?limit=5",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert "items" in j1 and isinstance(j1["items"], list)

    if not j1["items"]:
        # Nothing to paginate; still valid
        return

    # Cursor should exist if more results are available (implementation-dependent)
    cursor = j1.get("next_cursor") or j1.get("cursor") or j1.get("next")
    assert cursor, f"Expected a next cursor when items exist. Response: {j1}"

    # Page 2 should not duplicate Page 1 first item
    r2 = client.get(
        f"/v1/wallets/{wallet2_xof}/transactions?limit=5&cursor={cursor}",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert "items" in j2 and isinstance(j2["items"], list)

    ids_page1 = {item.get("entry_id") or item.get("id") for item in j1["items"]}
    ids_page2 = {item.get("entry_id") or item.get("id") for item in j2["items"]}
    # If your API uses entry_id cursoring, these IDs should never overlap
    assert ids_page1.isdisjoint(ids_page2), "Duplicate items across pages"


def test_activity_pagination_cursor_stable(client, user2, wallet2_xof):
    r1 = client.get(
        f"/v1/wallets/{wallet2_xof}/activity?limit=5",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert "items" in j1 and isinstance(j1["items"], list)

    if not j1["items"]:
        return

    cursor = j1.get("next_cursor") or j1.get("cursor") or j1.get("next")
    assert cursor, f"Expected a next cursor when items exist. Response: {j1}"

    r2 = client.get(
        f"/v1/wallets/{wallet2_xof}/activity?limit=5&cursor={cursor}",
        headers={"Authorization": f"Bearer {user2.token}"},
    )
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert "items" in j2 and isinstance(j2["items"], list)

    tx_ids_1 = {item.get("transaction_id") or item.get("id") for item in j1["items"]}
    tx_ids_2 = {item.get("transaction_id") or item.get("id") for item in j2["items"]}
    assert tx_ids_1.isdisjoint(tx_ids_2), "Duplicate activity items across pages"
