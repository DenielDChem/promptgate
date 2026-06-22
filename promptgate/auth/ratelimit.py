"""Minimal in-memory rate limiter (per process).

Sliding-window counter keyed by an arbitrary string. Adequate for a single
uvicorn worker. A multi-worker / multi-host deployment needs a shared store
(Redis) — tracked as future work in docs/PLATFORM_ARCHITECTURE.md.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Allow at most ``max_events`` per ``window_seconds`` per key.

    Examples:
        >>> rl = RateLimiter(max_events=2, window_seconds=60)
        >>> rl.allow("a"), rl.allow("a"), rl.allow("a")
        (True, True, False)
        >>> rl.allow("b")          # different key, independent budget
        True
    """

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self._max = max_events
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = [t for t in self._hits.get(key, ()) if t > cutoff]
            if len(bucket) >= self._max:
                self._hits[key] = bucket
                return False
            bucket.append(now)
            self._hits[key] = bucket
            return True

    def reset(self, key: str) -> None:
        """Clear a key's history (e.g. after a successful login)."""
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        """Drop all history (used by tests to isolate the shared limiter)."""
        with self._lock:
            self._hits.clear()
