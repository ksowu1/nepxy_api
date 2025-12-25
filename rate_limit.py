
import time
from collections import defaultdict, deque

# key -> deque[timestamps]
_hits = defaultdict(lambda: deque())

def allow(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    q = _hits[key]
    while q and (now - q[0]) > window_seconds:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True
