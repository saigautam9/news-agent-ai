"""
Tiny in-memory TTL cache.

The free-tier API quota (20 Gemini requests/day) is the binding constraint, so
identical requests within a short window are served from memory instead of
spending another call. The cache lives for the lifetime of the server process
— a deliberate, zero-cost design that needs no external store.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any


class TTLCache:
    """A thread-safe key/value cache where entries expire after `ttl` seconds."""

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl = ttl_seconds
        self._data: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, stored_at = entry
            if time.time() - stored_at > self.ttl:
                del self._data[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (value, time.time())
