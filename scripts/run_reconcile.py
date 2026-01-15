from __future__ import annotations

import argparse

from services.reconcile import run_reconcile


def main() -> None:
    parser = argparse.ArgumentParser(description="Run payout reconciliation once.")
    parser.add_argument("--stale-minutes", type=int, default=30)
    parser.add_argument("--lookback-minutes", type=int, default=240)
    args = parser.parse_args()

    result = run_reconcile(stale_minutes=args.stale_minutes, lookback_minutes=args.lookback_minutes)
    summary = result["summary"]

    print("reconcile_report_id:", result["id"])
    print(
        "counts:",
        f"status_mismatch={summary['status_mismatch']}",
        f"confirmed_missing_ledger={summary['confirmed_missing_ledger']}",
        f"ledger_missing_payout={summary['ledger_missing_payout']}",
        f"stale_checked={summary['stale_checked']}",
        f"confirmed_checked={summary['confirmed_checked']}",
        f"ledger_checked={summary['ledger_checked']}",
    )


if __name__ == "__main__":
    main()
