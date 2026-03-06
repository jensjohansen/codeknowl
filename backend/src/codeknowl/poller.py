"""File: backend/src/codeknowl/poller.py
Purpose: Provide a simple polling loop for accepted-branch repo updates (Milestone 3).
Product/business importance: Enables automatic background refresh of indexes to track accepted-branch changes.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from codeknowl.metrics import METRICS
from codeknowl.service import CodeKnowlService

_START_LOCK = threading.Lock()
_POLL_THREAD: threading.Thread | None = None


def start_repo_poller(*, data_dir: Path, interval_seconds: int) -> threading.Thread:
    """Start a daemon thread that polls all registered repos and updates them to accepted head."""

    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be > 0")

    global _POLL_THREAD
    with _START_LOCK:
        if _POLL_THREAD and _POLL_THREAD.is_alive():
            return _POLL_THREAD

    def _run() -> None:
        failure_counts: dict[str, int] = {}
        next_allowed_at: dict[str, float] = {}

        # Cap backoff so one broken repo doesn't go dark for too long.
        max_backoff_seconds = max(interval_seconds * 32, interval_seconds)

        while True:
            try:
                service = CodeKnowlService(data_dir=data_dir)
                repos = service.list_repos()
                for r in repos:
                    try:
                        now = time.time()
                        allow_at = next_allowed_at.get(r.repo_id, 0.0)
                        if now < allow_at:
                            METRICS.inc("poller.update.skipped_backoff")
                            continue

                        METRICS.inc("poller.update.attempt")
                        service.update_repo_to_accepted_head_sync(r.repo_id, blocking=False)
                        METRICS.inc("poller.update.succeeded")

                        failure_counts.pop(r.repo_id, None)
                        next_allowed_at.pop(r.repo_id, None)
                    except Exception:  # noqa: BLE001
                        METRICS.inc("poller.update.failed")
                        failures = failure_counts.get(r.repo_id, 0) + 1
                        failure_counts[r.repo_id] = failures

                        backoff = min(interval_seconds * (2**failures), max_backoff_seconds)
                        next_allowed_at[r.repo_id] = time.time() + backoff

                        METRICS.inc("poller.update.backoff_applied")
            except Exception:  # noqa: BLE001
                METRICS.inc("poller.loop.failed")
                pass

            time.sleep(interval_seconds)

    t = threading.Thread(target=_run, name="codeknowl-repo-poller", daemon=True)
    t.start()
    with _START_LOCK:
        _POLL_THREAD = t
    return t
