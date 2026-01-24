import argparse
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
    try:
        resp = _session.request(
            "POST",
            base_url + "/v1/admin/mobile-money/payouts/process-once",
            headers=auth_headers(admin_token),
            json={"batch_size": 1, "stale_seconds": 0},
            timeout=10,
        )
    except Exception as exc:
        print("Admin process-once error: %s" % exc)
        return False
    if resp.status_code in (200, 201):
        return True
    print("Admin process-once failed (%s): %s" % (resp.status_code, resp.text))
    return False


def _poll_until_terminal(base_url, token, admin_token, tx_id, poll_seconds, poll_interval):
    end_at = time.time() + poll_seconds
    last_status = None
    transitions = []
    payout = {}
    while time.time() < end_at:
        if admin_token:
            _process_payouts_once(base_url, admin_token)
        r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
        payout = r.json()
        status = payout.get("status")
        if status != last_status:
            print("status=%s provider=%s provider_ref=%s" % (status, payout.get("provider"), payout.get("provider_ref")))
            transitions.append(status)
            last_status = status
        if status in ("CONFIRMED", "FAILED"):
            break
        time.sleep(poll_interval)
    return payout, transitions


def _parse_args():
    parser = argparse.ArgumentParser(description="Thunes staging canary")
    parser.add_argument("--country", required=True, help="destination country ISO2")
    parser.add_argument("--provider", default="THUNES", help="THUNES or AUTO")
    parser.add_argument("--phone", required=True, help="destination phone in E.164")
    parser.add_argument("--amount-cents", type=int, default=100)
    parser.add_argument("--cashin-cents", type=int, default=2000)
    parser.add_argument("--currency", default=None)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--poll-interval", type=int, default=2)
    parser.add_argument("--webhook", default="auto", help="auto|on|off")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wallet-id", default=None)
    return parser.parse_args()


def main():
    args = _parse_args()
    base_url = os.getenv("STAGING_BASE_URL") or os.getenv("BASE_URL")
    _configure_session()
    user_email = os.getenv("STAGING_USER_EMAIL") or os.getenv("USER_EMAIL")
    user_password = os.getenv("STAGING_USER_PASSWORD") or os.getenv("USER_PASSWORD")
    admin_email = os.getenv("STAGING_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    thunes_secret = os.getenv("THUNES_WEBHOOK_SECRET", "")

    missing = []
    if not base_url:
        missing.append("STAGING_BASE_URL or BASE_URL")
    if not user_email or not user_password:
        missing.append("STAGING_USER_EMAIL/STAGING_USER_PASSWORD or USER_EMAIL/USER_PASSWORD")
    if not admin_email or not admin_password:
        missing.append("STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD or ADMIN_EMAIL/ADMIN_PASSWORD")
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    provider_arg = (args.provider or "").strip().upper()
    provider_value = None if provider_arg == "AUTO" else provider_arg

    if args.dry_run:
        print("Dry run:")
        print("country=%s provider=%s phone=%s amount_cents=%s cashin_cents=%s currency=%s"
              % (args.country, provider_arg, args.phone, args.amount_cents, args.cashin_cents, args.currency))
        return

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
    wallet_id = args.wallet_id
    if not wallet_id:
        r = request("GET", base_url + "/v1/wallets", headers=auth_headers(token))
        wallets = r.json().get("wallets") or r.json()
        if not wallets:
            die("No wallets returned.")
        wallet_id = wallets[0].get("wallet_id") or wallets[0].get("id")
        if not wallet_id:
            die("Could not determine wallet_id.")

    if args.cashin_cents > 0:
        step("Cash-in %s" % args.cashin_cents)
        request(
            "POST",
            base_url + "/v1/cash-in/mobile-money",
            headers=auth_headers(token, new_idem_key()),
            json_body={
                "wallet_id": wallet_id,
                "amount_cents": args.cashin_cents,
                "country": "TG",
                "provider": "TMONEY",
                "phone_e164": "+22890009911",
            },
        )

    step("Cash-out %s (%s)" % (args.amount_cents, provider_arg))
    cashout_body = {
        "wallet_id": wallet_id,
        "amount_cents": args.amount_cents,
        "destination_country": args.country,
        "phone_e164": args.phone,
    }
    if provider_value:
        cashout_body["provider"] = provider_value
    if args.currency:
        cashout_body["currency"] = args.currency

    r = request(
        "POST",
        base_url + "/v1/cash-out/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body=cashout_body,
    )
    tx_id = r.json().get("transaction_id")
    if not tx_id:
        die("Missing transaction_id from cash-out.")

    step("Get payout and check status")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    external_ref = payout.get("external_ref")
    provider_ref = payout.get("provider_ref")
    provider = (payout.get("provider") or "").upper()
    if not external_ref:
        die("Missing external_ref on payout.")
    print("transaction_id=%s external_ref=%s provider_ref=%s provider=%s" % (tx_id, external_ref, provider_ref, provider))

    webhook_mode = (args.webhook or "auto").strip().lower()
    webhook_enabled = False
    if webhook_mode == "on":
        webhook_enabled = True
    elif webhook_mode == "auto":
        webhook_enabled = bool(thunes_secret)

    if webhook_enabled and provider == "THUNES":
        if not thunes_secret:
            die("THUNES_WEBHOOK_SECRET is required for --webhook=on")
        step("Post THUNES webhook")
        payload_obj = {"external_ref": external_ref, "status": "SUCCESSFUL"}
        payload_bytes = canonical_json_bytes(payload_obj)
        headers = {"Content-Type": "application/json", **_sign_thunes(thunes_secret, payload_bytes)}
        if os.getenv("WEBHOOK_DEBUG") == "1":
            print("THUNES webhook body_len=%s sig=%s" % (len(payload_bytes), headers["X-Signature"][:12]))
        request(
            "POST",
            base_url + "/v1/webhooks/thunes",
            headers=headers,
            data=payload_bytes,
        )
    elif webhook_enabled:
        print("Skipping webhook post; provider is %s." % provider)

    step("Poll payout")
    payout, transitions = _poll_until_terminal(
        base_url,
        token,
        admin_token,
        tx_id,
        poll_seconds=args.poll_seconds,
        poll_interval=args.poll_interval,
    )
    status = payout.get("status")
    if status not in ("CONFIRMED", "FAILED"):
        die("Payout not terminal. Current status: %s" % status)

    event_count = 0
    if webhook_enabled and provider == "THUNES":
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
        event_count = len(events)
    else:
        print("Skipping admin webhook events check.")

    step("Thunes canary completed")
    print("transaction_id=%s" % tx_id)
    print("external_ref=%s" % external_ref)
    print("provider_ref=%s" % provider_ref)
    print("status=%s transitions=%s webhook_events=%s" % (status, ",".join(transitions), event_count))


if __name__ == "__main__":
    main()
