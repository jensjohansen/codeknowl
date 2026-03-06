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
    """Resolve a git ref to a commit hash.

    Why this exists:
    - Indexing and updates need to resolve refs (HEAD, remote branches) to stable commit identifiers.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_head_commit(repo_path: Path) -> str:
    """Return the current HEAD commit hash.

    Why this exists:
    - Initial indexing needs to capture the current snapshot identifier.
    """
    return rev_parse(repo_path, "HEAD")


def fetch_remote(repo_path: Path, remote: str) -> None:
    """Fetch updates from a remote.

    Why this exists:
    - Accepted-code-first updates need to ensure the remote refs are up-to-date before resolution.
    """
    subprocess.run(
        ["git", "-C", str(repo_path), "fetch", remote],
        capture_output=True,
        text=True,
        check=True,
    )


def diff_name_status(repo_path: Path, old_commit: str, new_commit: str) -> list[tuple[str, str]]:
    """Return a list of (status, path) for changed files between two commits.

    Why this exists:
    - Incremental updates need to know which files were added, modified, or deleted.
    """
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
    """Create a detached worktree for a specific commit.

    Why this exists:
    - Indexing and updates need a temporary, stable checkout of a specific commit without affecting the main repo.
    """
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
    """Remove a worktree, ignoring errors.

    Why this exists:
    - Cleanup after temporary checkouts must not raise exceptions if the worktree was already removed.
    """
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "remove", "--force", str(worktree_path)],
        capture_output=True,
        text=True,
        check=False,
    )
