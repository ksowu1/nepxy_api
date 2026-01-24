
import math
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits = defaultdict(lambda: deque())
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        q = self._hits[key]
        while q and (now - q[0]) > window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry_after = max(1, int(math.ceil(window_seconds - (now - q[0]))))
            return False, retry_after
        q.append(now)
        return True, 0

    def allow_token_bucket(self, key: str, capacity: int, refill_per_sec: float) -> bool:
        now = time.time()
        tokens, last = self._buckets.get(key, (float(capacity), now))

        elapsed = max(0.0, now - last)
        tokens = min(float(capacity), tokens + elapsed * refill_per_sec)

        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False

        self._buckets[key] = (tokens - 1.0, now)
        return True

    def reset(self) -> None:
        self._hits.clear()
        self._buckets.clear()


_limiter = InMemoryRateLimiter()


def rate_limit_enabled() -> bool:
    return (os.getenv("RATE_LIMIT_ENABLED") or "0").strip() == "1"


def rate_limit_login_per_min() -> int:
    raw = (os.getenv("RATE_LIMIT_LOGIN_PER_MIN") or "10").strip()
    return int(raw) if raw.isdigit() else 10


def rate_limit_money_per_min() -> int:
    raw = (os.getenv("RATE_LIMIT_MONEY_PER_MIN") or "30").strip()
    return int(raw) if raw.isdigit() else 30


def rate_limit_webhook_per_min() -> int:
    raw = (os.getenv("RATE_LIMIT_WEBHOOK_PER_MIN") or "60").strip()
    return int(raw) if raw.isdigit() else 60


def rate_limit_or_429(*, key: str, limit: int, window_seconds: int) -> None:
    ok, retry_after = _limiter.allow(key, limit, window_seconds)
    if ok:
        return
    headers = {"Retry-After": str(retry_after)}
    raise HTTPException(status_code=429, detail="RATE_LIMITED", headers=headers)


# Back-compat helpers for middleware usage.
def allow(key: str, limit: int, window_seconds: int) -> bool:
    ok, _ = _limiter.allow(key, limit, window_seconds)
    return ok


def allow_token_bucket(key: str, capacity: int, refill_per_sec: float) -> bool:
    return _limiter.allow_token_bucket(key, capacity, refill_per_sec)
