"""Simple in-memory rate limiting utilities."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict


@dataclass
class _Bucket:
    timestamps: Deque[float]


class InMemoryRateLimiter:
    """Fixed-window rate limiter suitable for single-node deployments."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, _Bucket] = {}

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(key, _Bucket(timestamps=deque()))
            while bucket.timestamps and bucket.timestamps[0] < cutoff:
                bucket.timestamps.popleft()

            if len(bucket.timestamps) >= limit:
                return False

            bucket.timestamps.append(now)
            return True

    def remaining(self, key: str, limit: int, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets.setdefault(key, _Bucket(timestamps=deque()))
            while bucket.timestamps and bucket.timestamps[0] < cutoff:
                bucket.timestamps.popleft()
            return max(0, limit - len(bucket.timestamps))


rate_limiter = InMemoryRateLimiter()
