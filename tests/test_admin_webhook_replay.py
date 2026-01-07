

import json
import uuid
import hmac
import hashlib

def _sign(body_bytes: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

def test_admin_can_list_webhook_events(client, admin):
    r = client.get("/v1/admin/webhooks/events?limit=5", headers={"Authorization": f"Bearer {admin.token}"})
    assert r.status_code == 200, r.text
    assert "events" in r.json()

def test_admin_can_replay_webhook_event(client, admin, user1, wallet1_xof, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")

    # create payout then send signed webhook
    # (reuse your existing helper patterns if you want; keeping minimal here)

    # cash-in
    r = client.post(
        "/v1/cash-in/mobile-money",
        json={
            "wallet_id": wallet1_xof,
            "amount_cents": 2000,
            "country": "TG",
            "provider_ref": f"pytest-cashin-{uuid.uuid4()}",
            "provider": "TMONEY",
        },
        headers={"Authorization": f"Bearer {user1.token}", "Idempotency-Key": f"idem-{uuid.uuid4()}"},
    )
    assert r.status_code in (200, 201), r.text

    # cash-out
    r = client.post(
        "/v1/cash-out/mobile-money",
        json={
            "wallet_id": wallet1_xof,
            "amount_cents": 100,
            "country": "TG",
            "provider_ref": f"cashout-{uuid.uuid4()}",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
        headers={"Authorization": f"Bearer {user1.token}", "Idempotency-Key": f"idem-{uuid.uuid4()}"},
    )
    assert r.status_code in (200, 201), r.text
    tx_id = r.json()["transaction_id"]

    payout = client.get(f"/v1/payouts/{tx_id}", headers={"Authorization": f"Bearer {user1.token}"}).json()
    ext = payout["external_ref"]

    body = {"external_ref": ext, "status": "SUCCESS"}
    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_tmoney")

    r = client.post("/v1/webhooks/tmoney", content=body_bytes, headers={"Content-Type": "application/json", "X-Signature": sig})
    assert r.status_code == 200, r.text

    # find latest event id for this external_ref
    r = client.get(
        f"/v1/admin/webhooks/events?provider=TMONEY&external_ref={ext}&limit=1",
        headers={"Authorization": f"Bearer {admin.token}"},
    )
    assert r.status_code == 200, r.text
    events = r.json()["events"]
    assert events and events[0]["id"]
    event_id = events[0]["id"]

    # replay should be idempotent (likely ignored already confirmed)
    r = client.post(
        f"/v1/admin/webhooks/events/{event_id}/replay",
        headers={"Authorization": f"Bearer {admin.token}"},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
