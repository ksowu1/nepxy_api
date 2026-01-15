# scripts/reconcile_daemon.py
from __future__ import annotations

import logging
import os
import time

from services.reconcile import run_reconcile


logger = logging.getLogger("reconcile_daemon")


def _interval_seconds() -> int:
    raw = os.getenv("RECONCILE_INTERVAL_SECONDS", "300")
    try:
        value = int(raw)
    except ValueError:
        return 300
    return max(1, value)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    interval = _interval_seconds()
    logger.info("Reconcile daemon starting; interval=%ss", interval)

    while True:
        try:
            result = run_reconcile()
        except KeyboardInterrupt:
            logger.info("Reconcile daemon exiting")
            raise
        except Exception:
            logger.exception("Reconcile daemon failed")
            raise

        summary = result.get("summary") or {}
        logger.info(
            "Reconcile report %s | stale_checked=%s status_mismatch=%s confirmed_missing_ledger=%s ledger_missing_payout=%s",
            result.get("id"),
            summary.get("stale_checked"),
            summary.get("status_mismatch"),
            summary.get("confirmed_missing_ledger"),
            summary.get("ledger_missing_payout"),
        )
        time.sleep(interval)


if __name__ == "__main__":
    main()
