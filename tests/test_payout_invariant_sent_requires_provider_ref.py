


# tests/test_payout_invariant_no_poll_without_provider_ref.py

from types import SimpleNamespace

import app.workers.payout_worker as payout_worker
from db import get_conn


def _insert_sent_payout_missing_ref(provider="TMONEY", phone_e164="+22890001122"):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app.mobile_money_payouts
              (id, transaction_id, provider, phone_e164, provider_ref, status,
               amount_cents, currency,
               attempt_count, created_at, updated_at)
            VALUES
              (gen_random_uuid(), gen_random_uuid(), %s, %s, NULL, 'SENT',
               1000, 'XOF',
               0, NOW(), NOW())
            RETURNING id
            """,
            (provider, phone_e164),
        )

        payout_id = cur.fetchone()[0]
        conn.commit()
        return payout_id


def test_worker_does_not_poll_without_provider_ref(monkeypatch):
    calls = {"send": 0, "status": 0}

    TARGET_PHONE = "+22890001122"

    class ProviderSpy:
        def send_cashout(self, payout):
            if payout.get("phone_e164") == TARGET_PHONE:
                calls["send"] += 1
            return SimpleNamespace(
                ok=False,
                error="Gateway timeout",
                response={"http_status": 504},
            )

        def get_cashout_status(self, payout):
            if payout.get("phone_e164") == TARGET_PHONE:
                calls["status"] += 1
            return SimpleNamespace(
                ok=True,
                provider_tx_id="should-not-be-called",
                response={"http_status": 200},
            )

    monkeypatch.setattr(payout_worker, "get_provider", lambda name: ProviderSpy())

    _insert_sent_payout_missing_ref(provider="TMONEY", phone_e164="+22890001122")

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    assert calls["send"] >= 1
    assert calls["status"] == 0
