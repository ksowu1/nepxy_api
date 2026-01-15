import json
import os
import sys
import uuid
import hmac
import hashlib

import requests


def die(message, code=1):
    print(message)
    sys.exit(code)


def step(message):
    print("\n==> " + message)


def request(method, url, headers=None, json_body=None, data=None):
    try:
        resp = requests.request(method, url, headers=headers, json=json_body, data=data)
    except Exception as exc:
        die("Request failed: %s" % exc)
    if resp.status_code < 200 or resp.status_code >= 300:
        print("HTTP %s %s" % (resp.status_code, resp.reason))
        print(resp.text)
        sys.exit(1)
    return resp


def auth_headers(token, idem=None):
    h = {"Authorization": "Bearer %s" % token}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def new_idem_key():
    return "idem-" + uuid.uuid4().hex


def sign_tmoney(payload_bytes, secret):
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return "sha256=" + mac


def main():
    base_url = os.getenv("STAGING_BASE_URL") or os.getenv("BASE_URL")
    user_email = os.getenv("STAGING_USER_EMAIL")
    user_password = os.getenv("STAGING_USER_PASSWORD")
    admin_email = os.getenv("STAGING_ADMIN_EMAIL")
    admin_password = os.getenv("STAGING_ADMIN_PASSWORD")
    webhook_secret = (
        os.getenv("STAGING_TMONEY_WEBHOOK_SECRET")
        or os.getenv("TMONEY_WEBHOOK_SECRET")
    )

    missing = [
        name
        for name in (
            "STAGING_BASE_URL",
            "STAGING_USER_EMAIL",
            "STAGING_USER_PASSWORD",
            "STAGING_ADMIN_EMAIL",
            "STAGING_ADMIN_PASSWORD",
        )
        if not os.getenv(name)
    ]
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    if not base_url:
        die("Missing STAGING_BASE_URL or BASE_URL")
    if not webhook_secret:
        die("Missing STAGING_TMONEY_WEBHOOK_SECRET or TMONEY_WEBHOOK_SECRET")

    step("Login user")
    r = request(
        "POST",
        base_url + "/v1/auth/login",
        json_body={"email": user_email, "password": user_password},
    )
    token = r.json().get("access_token")
    if not token:
        die("Missing access_token for user.")

    step("Login admin")
    r = request(
        "POST",
        base_url + "/v1/auth/login",
        json_body={"email": admin_email, "password": admin_password},
    )
    admin_token = r.json().get("access_token")
    if not admin_token:
        die("Missing access_token for admin.")

    step("Fetch wallet")
    r = request("GET", base_url + "/v1/wallets", headers=auth_headers(token))
    wallets = []
    payload = r.json()
    if isinstance(payload, dict) and "wallets" in payload:
        wallets = payload.get("wallets") or []
    elif isinstance(payload, list):
        wallets = payload
    if not wallets:
        die("No wallets returned.")
    wallet_id = wallets[0].get("wallet_id") or wallets[0].get("id")
    if not wallet_id:
        die("Could not determine wallet_id.")

    step("Cash-in 2000")
    request(
        "POST",
        base_url + "/v1/cash-in/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 2000,
            "country": "TG",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
    )

    step("Cash-out 100")
    r = request(
        "POST",
        base_url + "/v1/cash-out/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 100,
            "country": "BJ",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
    )
    tx_id = r.json().get("transaction_id")
    if not tx_id:
        die("Missing transaction_id from cash-out.")

    step("Get payout and check status")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    status = payout.get("status")
    if status not in ("PENDING", "SENT"):
        die("Unexpected payout status: %s" % status)

    external_ref = payout.get("external_ref")
    if not external_ref:
        die("Missing external_ref on payout.")

    step("Post TMONEY webhook")
    payload_obj = {"external_ref": external_ref, "status": "SUCCESS"}
    payload_json = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False)
    payload_bytes = payload_json.encode("utf-8")
    sig = sign_tmoney(payload_bytes, webhook_secret)
    request(
        "POST",
        base_url + "/v1/webhooks/tmoney",
        headers={"Content-Type": "application/json", "X-Signature": sig},
        data=payload_bytes,
    )

    step("Confirm payout updated")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    if payout.get("status") != "CONFIRMED":
        die("Payout not confirmed. Current status: %s" % payout.get("status"))

    step("Check admin payout webhook events")
    r = request(
        "GET",
        base_url + "/v1/admin/mobile-money/payouts/%s/webhook-events?limit=50" % tx_id,
        headers=auth_headers(admin_token),
    )
    data = r.json()
    events = []
    if isinstance(data, dict):
        events = data.get("items") or data.get("events") or []
    elif isinstance(data, list):
        events = data
    if not events:
        die("No webhook events found for payout.")
    refs = [e.get("external_ref") or e.get("provider_ref") for e in events]
    if external_ref not in refs:
        die("Webhook events missing expected external_ref: %s" % external_ref)

    step("Canary smoke completed")
    print("transaction_id=%s" % tx_id)
    print("external_ref=%s" % external_ref)


if __name__ == "__main__":
    main()
