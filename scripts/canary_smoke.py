import json
import os
import sys
import uuid
import hashlib

import requests

_session = requests.Session()

from _webhook_signing import canonical_json_bytes, tmoney_signature_header


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


def request(method, url, headers=None, json_body=None, data=None):
    try:
        resp = _session.request(method, url, headers=headers, json=json_body, data=data)
    except Exception as exc:
        die("Request failed: %s" % exc)
    if resp.status_code < 200 or resp.status_code >= 300:
        print("HTTP %s %s" % (resp.status_code, resp.reason))
        print(resp.text)
        sys.exit(1)
    return resp


def request_raw(method, url, headers=None, json_body=None, data=None):
    try:
        return _session.request(method, url, headers=headers, json=json_body, data=data)
    except Exception as exc:
        die("Request failed: %s" % exc)


def auth_headers(token, idem=None):
    h = {"Authorization": "Bearer %s" % token}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def new_idem_key():
    return "idem-" + uuid.uuid4().hex


def maybe_bootstrap_users(base_url, bootstrap_secret):
    if not bootstrap_secret or os.getenv("CANARY_ALLOW_BOOTSTRAP") != "1":
        return None
    step("Bootstrap staging users")
    resp = request_raw(
        "POST",
        base_url + "/debug/bootstrap-staging-users",
        headers={"X-Bootstrap-Admin-Secret": bootstrap_secret},
    )
    if resp.status_code == 404:
        print("Bootstrap endpoint not available; trying bootstrap-admin fallback")
        admin_email = os.getenv("STAGING_ADMIN_EMAIL")
        admin_password = os.getenv("STAGING_ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            print("Missing STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD for fallback")
            return False
        fallback = request_raw(
            "POST",
            base_url + "/debug/bootstrap-admin",
            headers={"X-Bootstrap-Secret": bootstrap_secret},
            json_body={"email": admin_email, "password": admin_password},
        )
        if fallback.status_code != 200:
            print("Bootstrap fallback failed: HTTP %s %s" % (fallback.status_code, fallback.reason))
            print(fallback.text)
            return None
        print("Bootstrap fallback succeeded via /debug/bootstrap-admin")
        return "admin-fallback"
    if resp.status_code != 200:
        print("Bootstrap failed: HTTP %s %s" % (resp.status_code, resp.reason))
        print(resp.text)
        return None
    print("Bootstrap succeeded via /debug/bootstrap-staging-users")
    return "staging-users"


def login_with_optional_bootstrap(base_url, email, password, bootstrap_secret, base_email=None, base_password=None):
    resp = request_raw(
        "POST",
        base_url + "/v1/auth/login",
        json_body={"email": email, "password": password},
    )
    if resp.status_code == 200:
        return resp.json().get("access_token")

    detail = ""
    try:
        detail = resp.json().get("detail", "")
    except Exception:
        detail = resp.text or ""

    if resp.status_code == 401 and detail == "INVALID_CREDENTIALS":
        if bootstrap_secret and os.getenv("CANARY_ALLOW_BOOTSTRAP") == "1":
            print("Login failed with INVALID_CREDENTIALS; attempting bootstrap")
            bootstrap_mode = maybe_bootstrap_users(base_url, bootstrap_secret)
            if bootstrap_mode:
                print("Retrying login after bootstrap")
                retry_email = email
                retry_password = password
                if bootstrap_mode == "staging-users" and base_email and base_password:
                    print("Using base USER_/ADMIN_ credentials after bootstrap-staging-users")
                    retry_email = base_email
                    retry_password = base_password
                resp = request_raw(
                    "POST",
                    base_url + "/v1/auth/login",
                    json_body={"email": retry_email, "password": retry_password},
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")
        else:
            print("Login failed with INVALID_CREDENTIALS; bootstrap disabled")
            resp = request_raw(
                "POST",
                base_url + "/v1/auth/login",
                json_body={"email": email, "password": password},
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")

    print("HTTP %s %s" % (resp.status_code, resp.reason))
    print(resp.text)
    return None


def main():
    base_url = os.getenv("STAGING_BASE_URL") or os.getenv("BASE_URL")
    _configure_session()
    base_user_email = os.getenv("USER_EMAIL")
    base_user_password = os.getenv("USER_PASSWORD")
    base_admin_email = os.getenv("ADMIN_EMAIL")
    base_admin_password = os.getenv("ADMIN_PASSWORD")

    user_email = os.getenv("STAGING_USER_EMAIL") or base_user_email
    user_password = os.getenv("STAGING_USER_PASSWORD") or base_user_password
    admin_email = os.getenv("STAGING_ADMIN_EMAIL") or base_admin_email
    admin_password = os.getenv("STAGING_ADMIN_PASSWORD") or base_admin_password
    user_source = "STAGING_*" if os.getenv("STAGING_USER_EMAIL") else "USER_*"
    admin_source = "STAGING_*" if os.getenv("STAGING_ADMIN_EMAIL") else "ADMIN_*"
    bootstrap_secret = os.getenv("BOOTSTRAP_ADMIN_SECRET")
    webhook_secret = (
        os.getenv("TMONEY_WEBHOOK_SECRET")
        or os.getenv("STAGING_TMONEY_WEBHOOK_SECRET")
    )
    if webhook_secret:
        webhook_secret = webhook_secret.strip()

    missing = []
    if not base_url:
        missing.append("STAGING_BASE_URL or BASE_URL")
    if not user_email or not user_password:
        missing.append("STAGING_USER_EMAIL/STAGING_USER_PASSWORD or USER_EMAIL/USER_PASSWORD")
    if not admin_email or not admin_password:
        missing.append("STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD or ADMIN_EMAIL/ADMIN_PASSWORD")
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    if not webhook_secret:
        die("Missing TMONEY_WEBHOOK_SECRET or STAGING_TMONEY_WEBHOOK_SECRET")

    print("Using user credentials from %s" % user_source)
    print("Using admin credentials from %s" % admin_source)

    step("Login user")
    token = login_with_optional_bootstrap(
        base_url,
        user_email,
        user_password,
        bootstrap_secret,
        base_email=base_user_email,
        base_password=base_user_password,
    )
    if not token:
        die("Missing access_token for user.")

    step("Login admin")
    admin_token = login_with_optional_bootstrap(
        base_url,
        admin_email,
        admin_password,
        bootstrap_secret,
        base_email=base_admin_email,
        base_password=base_admin_password,
    )
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
    payload_bytes = canonical_json_bytes(payload_obj)
    sig_header = tmoney_signature_header(webhook_secret, payload_bytes)
    if os.getenv("WEBHOOK_DEBUG") == "1":
        digest = hashlib.sha256(payload_bytes).hexdigest()[:12]
        sig_preview = sig_header["X-Signature"][:12]
        print("TMONEY webhook debug body_len=%s sha=%s sig=%s" % (len(payload_bytes), digest, sig_preview))
    request(
        "POST",
        base_url + "/v1/webhooks/tmoney",
        headers={"Content-Type": "application/json", **sig_header},
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
