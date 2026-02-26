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


def get_db_path(data_dir: Path) -> Path:
    return data_dir / "codeknowl.db"


def connect(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path(data_dir))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repos (
            repo_id TEXT PRIMARY KEY,
            local_path TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
        """
    )

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
