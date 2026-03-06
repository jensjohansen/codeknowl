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
    """In-memory counters for basic operator visibility.

    Why this exists:
    - The backend needs a minimal observability surface for Milestone 4 without requiring an external metrics stack.
    - Callers increment counters during request handling; operators read a point-in-time snapshot via the API.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _counters: dict[str, int] = field(default_factory=dict)

    def inc(self, name: str, value: int = 1) -> None:
        """Increment a named counter.

        Why this exists:
        - Request handlers and background loops need a concurrency-safe way to record throughput and failures.
        """
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        """Return a copy of all counters.

        Why this exists:
        - The `/metrics` endpoint needs a stable, serialization-safe view of current counters.
        """
        with self._lock:
            return dict(self._counters)


METRICS = Metrics()
