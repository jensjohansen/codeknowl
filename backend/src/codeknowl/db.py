"""File: backend/src/codeknowl/db.py
Purpose: Provide dev-local persistence for repo registration and index run status using SQLite.
Product/business importance: Tracks indexing state (last indexed commit/run status) required by Milestone 1
acceptance criteria.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _ensure_column(conn: sqlite3.Connection, *, table: str, column: str, ddl_fragment: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column in cols:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_fragment}")


def get_db_path(data_dir: Path) -> Path:
    """Return the filesystem path to the SQLite database file.

    Why this exists:
    - Callers need a single, consistent location for dev-local persistence so repo registration and indexing status
      can be resumed across process restarts.
    """
    return data_dir / "codeknowl.db"


def connect(data_dir: Path) -> sqlite3.Connection:
    """Open a SQLite connection for the backend's local-first state.

    Why this exists:
    - The backend needs a lightweight persistence layer for MVP milestones without requiring a separate database.
    - Callers use this to ensure the data directory exists and to get a connection configured for row access.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path(data_dir))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create required tables and apply forward-only schema changes.

    Why this exists:
    - The backend must be able to start cleanly on a new machine and evolve the dev-local schema without manual
      operator steps.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repos (
            repo_id TEXT PRIMARY KEY,
            local_path TEXT NOT NULL,
            accepted_branch TEXT NOT NULL DEFAULT 'main',
            preferred_remote TEXT,
            created_at_utc TEXT NOT NULL
        )
        """
    )

    # Lightweight forward-only migrations for dev-local SQLite.
    _ensure_column(conn, table="repos", column="accepted_branch", ddl_fragment="TEXT NOT NULL DEFAULT 'main'")
    _ensure_column(conn, table="repos", column="preferred_remote", ddl_fragment="TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS index_runs (
            run_id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            error TEXT,
            head_commit TEXT,
            FOREIGN KEY(repo_id) REFERENCES repos(repo_id)
        )
        """
    )

    conn.commit()
