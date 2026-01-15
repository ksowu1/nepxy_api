
import time
from collections import defaultdict, deque

# key -> deque[timestamps]
_hits = defaultdict(lambda: deque())

# key -> (tokens, last_refill)
_buckets: dict[str, tuple[float, float]] = {}

# TODO: replace in-memory buckets with Redis for multi-worker production.


def allow(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    q = _hits[key]
    while q and (now - q[0]) > window_seconds:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def allow_token_bucket(key: str, capacity: int, refill_per_sec: float) -> bool:
    now = time.time()
    tokens, last = _buckets.get(key, (float(capacity), now))

    elapsed = max(0.0, now - last)
    tokens = min(float(capacity), tokens + elapsed * refill_per_sec)

    if tokens < 1.0:
        _buckets[key] = (tokens, now)
        return False

    _buckets[key] = (tokens - 1.0, now)
    return True
