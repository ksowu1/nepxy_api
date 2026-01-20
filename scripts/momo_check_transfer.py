import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.providers.momo import MomoProvider


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/momo_check_transfer.py <provider_ref>")
        sys.exit(2)

    provider_ref = sys.argv[1].strip()
    if not provider_ref:
        print("Usage: python scripts/momo_check_transfer.py <provider_ref>")
        sys.exit(2)

    provider = MomoProvider()
    resp = provider.get_transfer_status(provider_ref)

    if hasattr(resp, "status_code"):
        payload = _safe_json(resp)
        status = None
        if isinstance(payload, dict):
            status = (payload.get("status") or payload.get("financialTransactionStatus") or "").upper() or None
        print("http_status=%s" % resp.status_code)
        print("text=%s" % getattr(resp, "text", None))
        print("json=%s" % payload)
        print("status=%s" % status)
        return

    print("error=%s" % getattr(resp, "error", None))
    print("response=%s" % getattr(resp, "response", None))
    sys.exit(1)


if __name__ == "__main__":
    main()
