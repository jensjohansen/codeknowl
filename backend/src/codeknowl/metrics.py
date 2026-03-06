"""File: backend/src/codeknowl/metrics.py
Purpose: Lightweight in-memory counters for basic observability.
Product/business importance: Enables Milestone 4 operator visibility without external dependencies.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class Metrics:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _counters: dict[str, int] = field(default_factory=dict)

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)


METRICS = Metrics()
