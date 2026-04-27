"""plato_edge.deadband — P0/P1/P2 gate with minimal regex.

No NLP, no heavy deps. Pure Python stdlib.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Tuple, Union


class DeadbandGate:
    """Classify traffic into P0 (critical), P1 (standard), or P2 (low)."""

    P0 = 0
    P1 = 1
    P2 = 2

    __slots__ = ("_p0", "_p1", "_fallback")

    def __init__(
        self,
        p0_patterns: Optional[List[str]] = None,
        p1_patterns: Optional[List[str]] = None,
        fallback: int = P2,
    ) -> None:
        self._p0 = _compile(p0_patterns or [])
        self._p1 = _compile(p1_patterns or [])
        if fallback not in (self.P0, self.P1, self.P2):
            raise ValueError("fallback must be P0, P1, or P2")
        self._fallback = fallback

    def classify(self, data: Union[str, bytes]) -> int:
        """Return P0, P1, or P2 for *data*."""
        text = _to_str(data)
        for pat in self._p0:
            if pat.search(text):
                return self.P0
        for pat in self._p1:
            if pat.search(text):
                return self.P1
        return self._fallback

    def gate(
        self,
        data: Union[str, bytes],
        p0_cb: Optional[Callable[[str], None]] = None,
        p1_cb: Optional[Callable[[str], None]] = None,
        p2_cb: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Classify and optionally dispatch to callbacks."""
        level = self.classify(data)
        text = _to_str(data)
        if level == self.P0 and p0_cb:
            p0_cb(text)
        elif level == self.P1 and p1_cb:
            p1_cb(text)
        elif level == self.P2 and p2_cb:
            p2_cb(text)
        return level


# Default fleet patterns — minimal, fast.
_DEFAULT_P0 = [
    r"ALERT",
    r"CRIT",
    r"EMERG",
    r"FAULT",
    r"\bP0\b",
]
_DEFAULT_P1 = [
    r"WARN",
    r"STATUS",
    r"UPDATE",
    r"HEARTBEAT",
    r"\bP1\b",
]

_default_gate: Optional[DeadbandGate] = None


def classify(data: Union[str, bytes]) -> int:
    """Classify *data* using the default gate."""
    global _default_gate
    if _default_gate is None:
        _default_gate = DeadbandGate(p0_patterns=_DEFAULT_P0, p1_patterns=_DEFAULT_P1)
    return _default_gate.classify(data)


def _compile(patterns: List[str]) -> List["re.Pattern[str]"]:
    out: List[re.Pattern[str]] = []
    for p in patterns:
        try:
            out.append(re.compile(p, re.IGNORECASE))
        except re.error as exc:
            raise ValueError(f"invalid regex {p!r}: {exc}")
    return out


def _to_str(data: Union[str, bytes]) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data
