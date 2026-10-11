"""In-memory sliding-window rate limiter keyed by IP hash (single-process; use a gateway limit in multi-node)."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque


def ip_hash(ip: str) -> str:
    salt = os.getenv("IP_HASH_SALT", "dev-salt-change-me")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


class RateLimiter:
    def __init__(self):
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str, key: str, limit: int, window: float, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            q = self._hits[(bucket, key)]
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def limits(bucket: str) -> tuple[int, float]:
    if bucket == "people":
        return int(os.getenv("RATE_LIMIT_PEOPLE_MAX", "5")), float(os.getenv("RATE_LIMIT_WINDOW", "3600"))
    return int(os.getenv("RATE_LIMIT_POOL_MAX", "10")), float(os.getenv("RATE_LIMIT_WINDOW", "3600"))
