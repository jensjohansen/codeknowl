"""File: backend/src/codeknowl/service.py
Purpose: Implement the backend service layer for repo registration, indexing, artifact generation, and Q&A.
Product/business importance: This is the core orchestration layer that enables Milestone 1 indexing and
evidence-grounded answers.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codeknowl import db
from codeknowl.artifacts import dump_dataclasses, repo_snapshot_dir, write_json
from codeknowl.ask import answer_with_llm
from codeknowl.indexing import build_file_inventory, extract_symbols_and_calls
from codeknowl.llm import LlmConfig, OpenAiCompatibleClient
from codeknowl.query import (
    explain_file_stub,
    find_callers_best_effort,
    load_snapshot_artifacts,
    where_is_symbol_defined,
)
from codeknowl.repo import get_head_commit


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RepoRecord:
    repo_id: str
    local_path: str
    created_at_utc: str


@dataclass(frozen=True)
class IndexRunRecord:
    run_id: str
    repo_id: str
    status: str
    started_at_utc: str
    finished_at_utc: str | None
    error: str | None
    head_commit: str | None


class CodeKnowlService:
    """Core backend service for repo registration, indexing, and query handling."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._conn = db.connect(data_dir)
        db.init_schema(self._conn)

    def register_repo_local_path(self, local_path: Path) -> RepoRecord:
        repo_id = str(uuid.uuid4())
        created_at_utc = _utc_now_iso()
        self._conn.execute(
            "INSERT INTO repos (repo_id, local_path, created_at_utc) VALUES (?, ?, ?)",
            (repo_id, str(local_path), created_at_utc),
        )
        self._conn.commit()
        return RepoRecord(repo_id=repo_id, local_path=str(local_path), created_at_utc=created_at_utc)

    def list_repos(self) -> list[RepoRecord]:
        rows = self._conn.execute("SELECT repo_id, local_path, created_at_utc FROM repos ORDER BY created_at_utc DESC")
        return [RepoRecord(**dict(row)) for row in rows.fetchall()]

    def start_index_run(self, repo_id: str) -> IndexRunRecord:
        run_id = str(uuid.uuid4())
        started_at_utc = _utc_now_iso()
        self._conn.execute(
            "INSERT INTO index_runs (run_id, repo_id, status, started_at_utc) VALUES (?, ?, ?, ?)",
            (run_id, repo_id, "running", started_at_utc),
        )
        self._conn.commit()
        return self.get_index_run(run_id)

    def complete_index_run(self, run_id: str, *, head_commit: str) -> IndexRunRecord:
        finished_at_utc = _utc_now_iso()
        self._conn.execute(
            "UPDATE index_runs SET status = ?, finished_at_utc = ?, head_commit = ? WHERE run_id = ?",
            ("succeeded", finished_at_utc, head_commit, run_id),
        )
        self._conn.commit()
        return self.get_index_run(run_id)

    def fail_index_run(self, run_id: str, *, error: str) -> IndexRunRecord:
        finished_at_utc = _utc_now_iso()
        self._conn.execute(
            "UPDATE index_runs SET status = ?, finished_at_utc = ?, error = ? WHERE run_id = ?",
            ("failed", finished_at_utc, error, run_id),
        )
        self._conn.commit()
        return self.get_index_run(run_id)

    def get_repo(self, repo_id: str) -> RepoRecord:
        row = self._conn.execute(
            "SELECT repo_id, local_path, created_at_utc FROM repos WHERE repo_id = ?",
            (repo_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Repo not found: {repo_id}")
        return RepoRecord(**dict(row))

    def get_index_run(self, run_id: str) -> IndexRunRecord:
        row = self._conn.execute(
            "SELECT run_id, repo_id, status, started_at_utc, finished_at_utc, error, head_commit "
            "FROM index_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Index run not found: {run_id}")
        return IndexRunRecord(**dict(row))

    def get_latest_index_run_for_repo(self, repo_id: str) -> IndexRunRecord | None:
        row = self._conn.execute(
            """
            SELECT run_id, repo_id, status, started_at_utc, finished_at_utc, error, head_commit
            FROM index_runs
            WHERE repo_id = ?
            ORDER BY started_at_utc DESC
            LIMIT 1
            """,
            (repo_id,),
        ).fetchone()
        if row is None:
            return None
        return IndexRunRecord(**dict(row))

    def run_indexing_sync(self, run_id: str) -> IndexRunRecord:
        repo = self.get_repo(self.get_index_run(run_id).repo_id)
        repo_path = Path(repo.local_path)

        try:
            head_commit = get_head_commit(repo_path)
        except Exception as exc:  # noqa: BLE001
            return self.fail_index_run(run_id, error=str(exc))

        try:
            files = build_file_inventory(repo_path)
            symbols, calls = extract_symbols_and_calls(repo_path)
            out_dir = repo_snapshot_dir(self._data_dir, repo.repo_id, head_commit)
            write_json(out_dir / "files.json", dump_dataclasses(files))
            write_json(out_dir / "symbols.json", dump_dataclasses(symbols))
            write_json(out_dir / "calls.json", dump_dataclasses(calls))
        except Exception as exc:  # noqa: BLE001
            return self.fail_index_run(run_id, error=str(exc))

        return self.complete_index_run(run_id, head_commit=head_commit)

    def repo_status(self, repo_id: str) -> dict[str, Any]:
        repo = self.get_repo(repo_id)
        latest = self.get_latest_index_run_for_repo(repo_id)
        return {
            "repo_id": repo.repo_id,
            "local_path": repo.local_path,
            "created_at_utc": repo.created_at_utc,
            "latest_index_run": None
            if latest is None
            else {
                "run_id": latest.run_id,
                "status": latest.status,
                "started_at_utc": latest.started_at_utc,
                "finished_at_utc": latest.finished_at_utc,
                "error": latest.error,
                "head_commit": latest.head_commit,
            },
        }

    def _get_latest_head_commit(self, repo_id: str) -> str:
        latest = self.get_latest_index_run_for_repo(repo_id)
        if latest is None or latest.status != "succeeded" or not latest.head_commit:
            raise ValueError("Repo has no successful index run")
        return latest.head_commit

    def _load_latest_artifacts(self, repo_id: str) -> tuple[str, dict[str, Any]]:
        head_commit = self._get_latest_head_commit(repo_id)
        return head_commit, load_snapshot_artifacts(self._data_dir, repo_id, head_commit)

    def qa_where_is_symbol_defined(self, repo_id: str, symbol_name: str) -> dict[str, Any]:
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "where_is_symbol_defined", "symbol_name": symbol_name},
            "results": where_is_symbol_defined(artifacts, symbol_name),
        }

    def qa_what_calls_symbol_best_effort(self, repo_id: str, callee_name: str) -> dict[str, Any]:
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "what_calls_symbol", "callee_name": callee_name, "mode": "best_effort"},
            "results": find_callers_best_effort(artifacts, callee_name),
        }

    def qa_explain_file_stub(self, repo_id: str, file_path: str) -> dict[str, Any]:
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "explain_file_stub", "file_path": file_path},
            "result": explain_file_stub(artifacts, file_path),
        }

    def qa_ask_llm(self, repo_id: str, question: str) -> dict[str, Any]:
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        llm = OpenAiCompatibleClient(LlmConfig.from_env())
        result = answer_with_llm(llm=llm, artifacts=artifacts, question=question)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "ask", "question": question},
            "answer": result.answer,
            "citations": result.citations,
            "evidence": result.evidence,
        }
