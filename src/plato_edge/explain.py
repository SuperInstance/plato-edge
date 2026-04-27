"""plato_edge.explain — stripped explainability (trace IDs only).

No full audit. Pure Python stdlib.
"""

from __future__ import annotations

import os
import struct
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class TraceError(ValueError):
    """Invalid trace operation."""


class Tracer:
    """Minimal tracer: generates trace IDs and keeps in-memory spans."""

    __slots__ = ("_spans", "_lock", "_max_spans")

    def __init__(self, max_spans: int = 1024) -> None:
        self._max_spans = max(1, max_spans)
        self._spans: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def trace_id() -> str:
        """Generate a short, unique trace ID."""
        # 8 bytes time + 4 bytes random = 12 bytes => 24 hex chars
        return (
            struct.pack(
                "<Q",
                int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF,
            )
            + os.urandom(4)
        ).hex()

    def start(self, name: str, trace_id: Optional[str] = None) -> Tuple[str, int]:
        """Start a span. Returns (trace_id, span_start_ns)."""
        tid = trace_id or self.trace_id()
        t0 = time.monotonic_ns()
        span = {
            "name": name,
            "t0": t0,
            "t1": None,
            "meta": {},
        }
        with self._lock:
            self._spans.setdefault(tid, [])
            if len(self._spans[tid]) >= self._max_spans:
                self._spans[tid].pop(0)
            self._spans[tid].append(span)
        return tid, t0

    def end(self, trace_id: str, t0: int, meta: Optional[Dict[str, Any]] = None) -> None:
        """End the most recent open span matching *t0*."""
        with self._lock:
            spans = self._spans.get(trace_id, [])
            for span in reversed(spans):
                if span["t0"] == t0 and span["t1"] is None:
                    span["t1"] = time.monotonic_ns()
                    if meta:
                        span["meta"].update(meta)
                    return
        raise TraceError("no open span found for trace_id/t0")

    def spans(self, trace_id: str) -> List[Dict[str, Any]]:
        """Return completed spans for *trace_id*."""
        with self._lock:
            return [
                dict(s)
                for s in self._spans.get(trace_id, [])
                if s["t1"] is not None
            ]

    def last(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Return the last completed span for *trace_id*."""
        with self._lock:
            spans = self._spans.get(trace_id, [])
            for s in reversed(spans):
                if s["t1"] is not None:
                    return dict(s)
            return None

    def drop(self, trace_id: str) -> bool:
        """Drop all spans for *trace_id*."""
        with self._lock:
            return bool(self._spans.pop(trace_id, None))

    def snapshot(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return shallow copy of all completed spans."""
        with self._lock:
            return {
                tid: [dict(s) for s in spans if s["t1"] is not None]
                for tid, spans in self._spans.items()
            }
