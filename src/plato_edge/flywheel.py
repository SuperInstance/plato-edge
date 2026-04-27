"""plato_edge.flywheel — in-memory pub/sub and key-value cache.

No persistence. Pure Python stdlib.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Set


class FlywheelError(RuntimeError):
    """Flywheel operation error."""


class Flywheel:
    """Lightweight in-memory event bus and key-value store."""

    __slots__ = ("_kv", "_subs", "_lock", "_max_kv", "_max_queue")

    def __init__(self, max_kv: int = 4096, max_queue: int = 256) -> None:
        self._max_kv = max(1, max_kv)
        self._max_queue = max(1, max_queue)
        self._kv: Dict[str, Any] = {}
        self._subs: Dict[str, Set[Callable[[Any], None]]] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store *value* under *key*. Optional *ttl* in seconds."""
        with self._lock:
            if len(self._kv) >= self._max_kv and key not in self._kv:
                # Evict oldest by arbitrary ordering (popitem last).
                self._kv.pop(next(iter(self._kv)))
            expiry = time.monotonic() + ttl if ttl is not None else None
            self._kv[key] = (value, expiry)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value for *key*."""
        with self._lock:
            entry = self._kv.get(key)
            if entry is None:
                return default
            value, expiry = entry
            if expiry is not None and time.monotonic() > expiry:
                del self._kv[key]
                return default
            return value

    def delete(self, key: str) -> bool:
        """Delete *key*. Return True if existed."""
        with self._lock:
            if key in self._kv:
                del self._kv[key]
                return True
            return False

    def publish(self, topic: str, message: Any) -> int:
        """Publish *message* to *topic*. Returns number of subscribers called."""
        cbs: List[Callable[[Any], None]] = []
        with self._lock:
            subs = self._subs.get(topic, set())
            cbs = list(subs)
        dropped = 0
        for cb in cbs:
            try:
                cb(message)
            except Exception:
                dropped += 1
        return len(cbs) - dropped

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """Subscribe *callback* to *topic*."""
        with self._lock:
            self._subs.setdefault(topic, set()).add(callback)

    def unsubscribe(self, topic: str, callback: Callable[[Any], None]) -> bool:
        """Unsubscribe *callback* from *topic*."""
        with self._lock:
            subs = self._subs.get(topic)
            if subs and callback in subs:
                subs.remove(callback)
                if not subs:
                    del self._subs[topic]
                return True
            return False

    def topics(self) -> List[str]:
        """Return known topics."""
        with self._lock:
            return list(self._subs.keys())

    def purge_expired(self) -> int:
        """Remove expired KV entries. Returns count removed."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            stale = [k for k, (_, e) in self._kv.items() if e is not None and now > e]
            for k in stale:
                del self._kv[k]
                removed += 1
        return removed

    def stats(self) -> Dict[str, int]:
        """Return basic stats."""
        with self._lock:
            return {
                "kv_count": len(self._kv),
                "topic_count": len(self._subs),
                "subscriber_count": sum(len(s) for s in self._subs.values()),
            }
