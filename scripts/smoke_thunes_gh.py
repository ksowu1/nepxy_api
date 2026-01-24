import os
import sys
import time
import uuid

import requests

from _webhook_signing import canonical_json_bytes, hmac_sha256_hex

_session = requests.Session()


def die(message, code=1):
    print(message)
    sys.exit(code)


def step(message):
    print("\n==> " + message)


def _configure_session():
    key = os.getenv("STAGING_GATE_KEY")
    if key:
        _session.headers.update({"X-Staging-Key": key})
        print("Using staging gate header")


def request(method, url, headers=None, json_body=None, data=None, allow_failure=False):
    try:
        resp = _session.request(method, url, headers=headers, json=json_body, data=data, timeout=20)
    except Exception as exc:
        die("Request failed: %s" % exc)
    if resp.status_code < 200 or resp.status_code >= 300:
        if not allow_failure:
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


def _sign_thunes(secret, body_bytes):
    return {"X-Signature": "sha256=" + hmac_sha256_hex(secret, body_bytes)}


def _process_payouts_once(base_url, admin_token):
    backoff = 2
    for attempt in range(1, 7):
        try:
            resp = _session.request(
                "POST",
                base_url + "/v1/admin/mobile-money/payouts/process-once",
                headers=auth_headers(admin_token),
                json={"batch_size": 1, "stale_seconds": 0},
                timeout=(5, 45),
            )
        except requests.RequestException as exc:
            print("Admin process-once attempt %s error: %s" % (attempt, exc.__class__.__name__))
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        if resp.status_code in (200, 201):
            return True
        if resp.status_code >= 500 and attempt < 6:
            print("Admin process-once attempt %s error: HTTP %s" % (attempt, resp.status_code))
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        print("Admin process-once failed (%s): %s" % (resp.status_code, resp.text))
        return False
    return False


def _poll_payout(base_url, token, admin_token, tx_id, poll_seconds=60, poll_interval=2):
    end_at = time.time() + poll_seconds
    last_status = None
    payout = {}
    while time.time() < end_at:
        _process_payouts_once(base_url, admin_token)
        r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
        payout = r.json()
        status = payout.get("status")
        if status != last_status:
            print("status=%s provider=%s provider_ref=%s" % (status, payout.get("provider"), payout.get("provider_ref")))
            last_status = status
        if status in ("SENT", "CONFIRMED", "FAILED"):
            break
        time.sleep(poll_interval)
    return payout


def main():
    base_url = os.getenv("STAGING_BASE_URL")
    _configure_session()

    user_email = os.getenv("STAGING_USER_EMAIL")
    user_password = os.getenv("STAGING_USER_PASSWORD")
    admin_email = os.getenv("STAGING_ADMIN_EMAIL")
    admin_password = os.getenv("STAGING_ADMIN_PASSWORD")
    thunes_secret = os.getenv("THUNES_WEBHOOK_SECRET", "")
    phone = os.getenv("THUNES_TEST_PHONE", "+233200000000")

    missing = []
    if not base_url:
        missing.append("STAGING_BASE_URL")
    if not user_email or not user_password:
        missing.append("STAGING_USER_EMAIL/STAGING_USER_PASSWORD")
    if not admin_email or not admin_password:
        missing.append("STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD")
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    step("Login user")
    r = request("POST", base_url + "/v1/auth/login", json_body={"email": user_email, "password": user_password})
    token = r.json().get("access_token")
    if not token:
        die("Missing access_token for user.")

    step("Login admin")
    r = request("POST", base_url + "/v1/auth/login", json_body={"email": admin_email, "password": admin_password})
    admin_token = r.json().get("access_token")
    if not admin_token:
        die("Missing access_token for admin.")

    step("Fetch wallet")
    r = request("GET", base_url + "/v1/wallets", headers=auth_headers(token))
    wallets = r.json().get("wallets") or r.json()
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

    step("Cash-out 100 (THUNES GH)")
    r = request(
        "POST",
        base_url + "/v1/cash-out/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 100,
            "country": "GH",
            "provider": "THUNES",
            "phone_e164": phone,
        },
    )
    tx_id = r.json().get("transaction_id")
    if not tx_id:
        die("Missing transaction_id from cash-out.")

    step("Get payout")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    external_ref = payout.get("external_ref")
    provider_ref = payout.get("provider_ref")
    if not external_ref:
        die("Missing external_ref on payout.")

    step("Poll payout until SENT/CONFIRMED")
    payout = _poll_payout(base_url, token, admin_token, tx_id)
    status = payout.get("status")
    if status not in ("SENT", "CONFIRMED"):
        print("last_error=%s" % payout.get("last_error"))
        provider_response = payout.get("provider_response")
        if provider_response is not None:
            print("provider_response=%s" % provider_response)
        die("Payout did not reach SENT/CONFIRMED (status=%s)" % status)

    step("Post THUNES webhook")
    if not thunes_secret:
        die("THUNES_WEBHOOK_SECRET is required for webhook validation.")
    payload_obj = {"external_ref": external_ref, "provider_ref": provider_ref, "status": "SUCCESSFUL"}
    payload_bytes = canonical_json_bytes(payload_obj)
    headers = {"Content-Type": "application/json", **_sign_thunes(thunes_secret, payload_bytes)}
    request("POST", base_url + "/v1/webhooks/thunes", headers=headers, data=payload_bytes)

    step("Poll payout until CONFIRMED")
    payout = _poll_payout(base_url, token, admin_token, tx_id)
    status = payout.get("status")
    if status != "CONFIRMED":
        die("Payout not confirmed (status=%s)" % status)

    step("Check admin payout webhook events")
    r = request(
        "GET",
        base_url + "/v1/admin/mobile-money/payouts/%s/webhook-events?limit=50" % tx_id,
        headers=auth_headers(admin_token),
    )
    data = r.json()
    events = data.get("items") or data.get("events") or data if isinstance(data, list) else []
    if not events:
        die("No webhook events found for payout.")
    refs = [e.get("external_ref") or e.get("provider_ref") for e in events]
    if external_ref not in refs and provider_ref not in refs:
        die("Webhook events missing expected refs: %s / %s" % (external_ref, provider_ref))

    print("Thunes GH smoke completed: tx_id=%s external_ref=%s provider_ref=%s" % (tx_id, external_ref, provider_ref))


if __name__ == "__main__":
    main()
