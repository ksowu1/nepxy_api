

# app/providers/mock.py
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional


class MockProvider:
    """
    Test/dev provider.

    IMPORTANT:
    - On failures, DO NOT default retryable=False, because the worker treats that as non-retryable.
    - Instead, leave retryable unset/None so the worker's classifier can use http_status (e.g. 504 => retry).
    """

    def __init__(
        self,
        *,
        succeed: bool = True,
        retryable: Optional[bool] = None,
        success_http_status: int = 200,
        failure_http_status: int = 504,
    ):
        self.succeed = succeed
        self.retryable = retryable  # None => let classifier decide
        self.success_http_status = success_http_status
        self.failure_http_status = failure_http_status

    def send_cashout(self, payout):
        if self.succeed:
            return SimpleNamespace(
                ok=True,
                provider_tx_id=f"mock-{payout.get('id')}",
                response={"http_status": self.success_http_status, "mock": True},
                error=None,
                retryable=None,
            )

        ns = SimpleNamespace(
            ok=False,
            provider_tx_id=None,
            response={"http_status": self.failure_http_status, "mock": True},
            error="Gateway timeout",
        )
        if self.retryable is not None:
            ns.retryable = self.retryable
        return ns

    def get_cashout_status(self, payout):
        if self.succeed:
            return SimpleNamespace(
                ok=True,
                provider_tx_id=payout.get("provider_ref") or f"mock-{payout.get('id')}",
                response={"http_status": 200, "status": "SUCCESSFUL", "mock": True},
                error=None,
                retryable=None,
            )

        ns = SimpleNamespace(
            ok=False,
            provider_tx_id=payout.get("provider_ref"),
            response={"http_status": 500, "mock": True},
            error="Server error",
        )
        if self.retryable is not None:
            ns.retryable = self.retryable
        return ns
