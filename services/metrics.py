from __future__ import annotations

from threading import Lock
from typing import Dict, Tuple


_lock = Lock()
_counters: dict[str, dict[Tuple[Tuple[str, str], ...], int]] = {}


def _inc(name: str, labels: dict[str, str] | None = None, value: int = 1) -> None:
    key = tuple(sorted((labels or {}).items()))
    with _lock:
        series = _counters.setdefault(name, {})
        series[key] = int(series.get(key, 0)) + int(value)


def increment_http_requests(route: str, status: int) -> None:
    _inc("http_requests_total", {"route": route, "status": str(status)})


def increment_payout_attempt(provider: str, result: str) -> None:
    _inc("payout_attempts_total", {"provider": provider, "result": result})


def increment_webhook_event(provider: str, signature_valid: bool, applied: bool) -> None:
    _inc(
        "webhook_events_total",
        {
            "provider": provider,
            "signature_valid": str(signature_valid).lower(),
            "applied": str(applied).lower(),
        },
    )


def increment_idempotency_replay(route: str) -> None:
    _inc("idempotency_replays_total", {"route": route})


def render_prometheus() -> str:
    lines: list[str] = []
    with _lock:
        for name, series in sorted(_counters.items()):
            lines.append(f"# TYPE {name} counter")
            for labels, value in sorted(series.items()):
                if labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                    lines.append(f"{name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")
    return "\n".join(lines) + ("\n" if lines else "")
