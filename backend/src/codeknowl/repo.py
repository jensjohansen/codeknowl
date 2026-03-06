"""File: backend/src/codeknowl/repo.py
Purpose: Provide git repository helpers (e.g., reading HEAD commit) used during indexing.
Product/business importance: Snapshot identity (commit hash) is required for reproducible indexing and citations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def rev_parse(repo_path: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_head_commit(repo_path: Path) -> str:
    return rev_parse(repo_path, "HEAD")


def fetch_remote(repo_path: Path, remote: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), "fetch", remote],
        capture_output=True,
        text=True,
        check=True,
    )


def diff_name_status(repo_path: Path, old_commit: str, new_commit: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "diff", "--name-status", f"{old_commit}..{new_commit}"],
        capture_output=True,
        text=True,
        check=True,
    )

    out: list[tuple[str, str]] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            # Represent rename as delete old + add new.
            out.append(("D", parts[1]))
            out.append(("A", parts[2]))
            continue
        if len(parts) >= 2:
            out.append((status, parts[1]))
    return out


def worktree_add_detached(repo_path: Path, worktree_path: Path, commit: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "worktree",
            "add",
            "--detach",
            str(worktree_path),
            commit,
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def worktree_remove(repo_path: Path, worktree_path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "remove", "--force", str(worktree_path)],
        capture_output=True,
        text=True,
        check=False,
    )
