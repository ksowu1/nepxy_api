

# tests/test_auth.py
def test_debug_me_user1(client, user1):
    r = client.get("/debug/me", headers={"Authorization": f"Bearer {user1.token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == user1.user_id


def test_debug_me_user2(client, user2):
    r = client.get("/debug/me", headers={"Authorization": f"Bearer {user2.token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == user2.user_id


def test_debug_me_invalid_token_unauthorized(client):
    r = client.get("/debug/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code in (401, 403), r.text
