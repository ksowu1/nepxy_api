


import uuid
import hmac
import hashlib
import json


def _hmac_sig(secret: str, body: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def test_webhook_missing_signature_401(client):
    body = {"external_ref": f"cashout-{uuid.uuid4()}", "status": "SUCCESS"}
    r = client.post("/v1/webhooks/tmoney", json=body)
    assert r.status_code == 401, r.text


def test_webhook_invalid_signature_401(client):
    body = {"external_ref": f"cashout-{uuid.uuid4()}", "status": "SUCCESS"}
    r = client.post("/v1/webhooks/tmoney", json=body, headers={"X-Signature": "sha256=deadbeef"})
    assert r.status_code == 401, r.text


def test_webhook_valid_signature_unknown_ref_200_ignored(client, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")
    body = {"external_ref": f"cashout-{uuid.uuid4()}", "status": "SUCCESS"}
    raw = json.dumps(body, separators=(",", ":"))
    sig = _hmac_sig("dev_secret_tmoney", raw)

    r = client.post(
        "/v1/webhooks/tmoney",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )

    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j.get("ignored") is True
    assert j.get("reason") == "PAYOUT_NOT_FOUND"
