from __future__ import annotations

import uuid

from tests.conftest import _auth_headers


def test_admin_roles_list(client, admin):
    r = client.get("/v1/admin/roles", headers=_auth_headers(admin.token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert any(item.get("role") == "ADMIN" for item in data["items"])


def test_admin_roles_list_includes_recent(admin_user, client):
    new_admin_id = admin_user.user_id
    r = client.get("/v1/admin/roles", headers=_auth_headers(admin_user.token))
    assert r.status_code == 200, r.text
    roles = {item["user_id"]: item["role"] for item in r.json().get("items", [])}
    assert roles.get(new_admin_id) == "ADMIN"
