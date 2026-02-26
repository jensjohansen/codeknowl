"""File: backend/src/codeknowl/repo.py
Purpose: Provide git repository helpers (e.g., reading HEAD commit) used during indexing.
Product/business importance: Snapshot identity (commit hash) is required for reproducible indexing and citations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_head_commit(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
