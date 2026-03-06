"""File: backend/src/codeknowl/service.py
Purpose: Implement the backend service layer for repo registration, indexing, artifact generation, and Q&A.
Product/business importance: This is the core orchestration layer that enables Milestone 1 indexing and
evidence-grounded answers.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from codeknowl import db
from codeknowl.artifacts import artifacts_root, dump_dataclasses, repo_snapshot_dir, write_json
from codeknowl.ask import answer_with_llm_synthesis, build_evidence_bundle
from codeknowl.chunking import ChunkRecord, chunk_repo_files, dump_chunks
from codeknowl.embeddings import embeddings_client_from_env
from codeknowl.indexing import (
    build_file_inventory,
    build_file_records_for_paths,
    extract_symbols_and_calls,
    extract_symbols_and_calls_for_paths,
    should_ignore_path,
)
from codeknowl.llm import LlmProfiles, OpenAiCompatibleClient
from codeknowl.metrics import METRICS
from codeknowl.query import (
    explain_file_stub,
    find_callers_best_effort,
    load_snapshot_artifacts,
    where_is_symbol_defined,
)
from codeknowl.repo import (
    diff_name_status,
    fetch_remote,
    get_head_commit,
    rev_parse,
    worktree_add_detached,
    worktree_remove,
)
from codeknowl.reranker import reranker_from_env
from codeknowl.vector_store import vector_store_from_env


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_UPDATE_LOCKS_LOCK = threading.Lock()
_UPDATE_LOCKS: dict[str, threading.Lock] = {}


def _get_update_lock(repo_id: str) -> threading.Lock:
    with _UPDATE_LOCKS_LOCK:
        lock = _UPDATE_LOCKS.get(repo_id)
        if lock is None:
            lock = threading.Lock()
            _UPDATE_LOCKS[repo_id] = lock
        return lock


@dataclass(frozen=True)
class RepoRecord:
    """Represents a repository registered with CodeKnowl.

    Why this exists:
    - The API/CLI needs a stable, serializable record of what repositories are in scope, how to locate them locally,
      and which branch is considered "accepted" for indexing and queries.
    """

    repo_id: str
    local_path: str
    accepted_branch: str
    preferred_remote: str | None
    created_at_utc: str


@dataclass(frozen=True)
class IndexRunRecord:
    """Represents a single indexing or update run for a repository.

    Why this exists:
    - Operators and IDE users need a queryable history of indexing outcomes (running/succeeded/failed) and the
      snapshot commit associated with the run.
    """

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
        self._vector_store = vector_store_from_env(data_dir=data_dir)
        self._embeddings = embeddings_client_from_env()
        self._reranker = reranker_from_env()

    def _index_semantic_snapshot(
        self,
        *,
        repo: RepoRecord,
        head_commit: str,
        file_paths: list[str],
    ) -> list[ChunkRecord]:
        if not file_paths:
            return []
        with TemporaryDirectory(prefix=f"codeknowl-wt-sem-{repo.repo_id[:8]}-") as td:
            wt = Path(td)
            worktree_add_detached(Path(repo.local_path), wt, head_commit)
            try:
                chunks = chunk_repo_files(
                    repo_id=repo.repo_id,
                    head_commit=head_commit,
                    repo_path=wt,
                    file_paths=file_paths,
                )
            finally:
                worktree_remove(Path(repo.local_path), wt)

        texts = [c.text for c in chunks]
        if not texts:
            return chunks

        vectors = self._embeddings.embed_texts(texts)
        self._vector_store.upsert(repo_id=repo.repo_id, head_commit=head_commit, chunks=chunks, vectors=vectors)
        return chunks

    def register_repo_local_path(
        self,
        local_path: Path,
        *,
        accepted_branch: str,
        preferred_remote: str | None,
    ) -> RepoRecord:
        """Register a repository using a local filesystem path.

        Why this exists:
        - The MVP onboarding flow is local-first: operators and IDE users point CodeKnowl at an already-cloned
          working copy, and CodeKnowl persists the registration so indexing and queries can be repeated.
        """
        repo_id = str(uuid.uuid4())
        created_at_utc = _utc_now_iso()
        self._conn.execute(
            "INSERT INTO repos (repo_id, local_path, accepted_branch, preferred_remote, created_at_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (repo_id, str(local_path), accepted_branch, preferred_remote, created_at_utc),
        )
        self._conn.commit()
        return RepoRecord(
            repo_id=repo_id,
            local_path=str(local_path),
            accepted_branch=accepted_branch,
            preferred_remote=preferred_remote,
            created_at_utc=created_at_utc,
        )

    def list_repos(self) -> list[RepoRecord]:
        """List registered repositories.

        Why this exists:
        - The IDE and operators need to discover repo scope and present choices for repo-scoped operations.
        """
        rows = self._conn.execute(
            "SELECT repo_id, local_path, accepted_branch, preferred_remote, created_at_utc "
            "FROM repos ORDER BY created_at_utc DESC"
        )
        return [RepoRecord(**dict(row)) for row in rows.fetchall()]

    def offboard_repo(self, repo_id: str) -> None:
        """Remove a repository from CodeKnowl so it is no longer queryable.

        Why this exists:
        - Off-boarding is required by the PRD so operators can explicitly remove repos from query scope (e.g.,
          migrations, decommissioning, or policy changes).
        """
        repo = self.get_repo(repo_id)
        self._conn.execute("DELETE FROM index_runs WHERE repo_id = ?", (repo.repo_id,))
        self._conn.execute("DELETE FROM repos WHERE repo_id = ?", (repo.repo_id,))
        self._conn.commit()

        root = artifacts_root(self._data_dir) / repo.repo_id
        if root.exists():
            for p in sorted(root.rglob("*"), reverse=True):
                if p.is_file() or p.is_symlink():
                    try:
                        p.unlink()
                    except OSError:
                        pass
                elif p.is_dir():
                    try:
                        p.rmdir()
                    except OSError:
                        pass
            try:
                root.rmdir()
            except OSError:
                pass

    def start_index_run(self, repo_id: str) -> IndexRunRecord:
        """Create an index run record in the running state.

        Why this exists:
        - Indexing needs operator-visible status. This method creates durable state before the actual work starts.
        """
        run_id = str(uuid.uuid4())
        started_at_utc = _utc_now_iso()
        self._conn.execute(
            "INSERT INTO index_runs (run_id, repo_id, status, started_at_utc) VALUES (?, ?, ?, ?)",
            (run_id, repo_id, "running", started_at_utc),
        )
        self._conn.commit()
        return self.get_index_run(run_id)

    def complete_index_run(self, run_id: str, *, head_commit: str) -> IndexRunRecord:
        """Mark a previously started index run as succeeded.

        Why this exists:
        - Downstream queries depend on knowing the last successfully indexed snapshot.
        """
        finished_at_utc = _utc_now_iso()
        self._conn.execute(
            "UPDATE index_runs SET status = ?, finished_at_utc = ?, head_commit = ? WHERE run_id = ?",
            ("succeeded", finished_at_utc, head_commit, run_id),
        )
        self._conn.commit()
        return self.get_index_run(run_id)

    def fail_index_run(self, run_id: str, *, error: str) -> IndexRunRecord:
        """Mark a previously started index run as failed.

        Why this exists:
        - Operators need failure visibility and the system must not silently treat failed runs as current.
        """
        finished_at_utc = _utc_now_iso()
        self._conn.execute(
            "UPDATE index_runs SET status = ?, finished_at_utc = ?, error = ? WHERE run_id = ?",
            ("failed", finished_at_utc, error, run_id),
        )
        self._conn.commit()
        return self.get_index_run(run_id)

    def get_repo(self, repo_id: str) -> RepoRecord:
        """Load a repository registration by repo_id.

        Why this exists:
        - Most repo-scoped operations (indexing, update, QA) need to resolve the local path and policy fields.
        """
        row = self._conn.execute(
            "SELECT repo_id, local_path, accepted_branch, preferred_remote, created_at_utc "
            "FROM repos WHERE repo_id = ?",
            (repo_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Repo not found: {repo_id}")
        return RepoRecord(**dict(row))

    def get_index_run(self, run_id: str) -> IndexRunRecord:
        """Load an index run record by run_id.

        Why this exists:
        - Status endpoints need to return the authoritative record for a run.
        """
        row = self._conn.execute(
            "SELECT run_id, repo_id, status, started_at_utc, finished_at_utc, error, head_commit "
            "FROM index_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Index run not found: {run_id}")
        return IndexRunRecord(**dict(row))

    def get_latest_index_run_for_repo(self, repo_id: str) -> IndexRunRecord | None:
        """Return the most recent index run for a repo, if any.

        Why this exists:
        - Status reporting must reflect the latest attempt, not only the last success.
        """
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

    def get_latest_successful_index_run_for_repo(self, repo_id: str) -> IndexRunRecord | None:
        """Return the most recent successful index run for a repo, if any.

        Why this exists:
        - Query answers must be grounded in a known-good snapshot; this identifies the latest usable commit.
        """
        row = self._conn.execute(
            """
            SELECT run_id, repo_id, status, started_at_utc, finished_at_utc, error, head_commit
            FROM index_runs
            WHERE repo_id = ? AND status = 'succeeded' AND head_commit IS NOT NULL
            ORDER BY started_at_utc DESC
            LIMIT 1
            """,
            (repo_id,),
        ).fetchone()
        if row is None:
            return None
        return IndexRunRecord(**dict(row))

    def run_indexing_sync(self, run_id: str) -> IndexRunRecord:
        """Perform a full indexing run for a repository snapshot.

        Why this exists:
        - This is the MVP execution path for initial indexing: it builds deterministic artifacts (files/symbols/calls),
          produces semantic chunks/embeddings, and records the resulting snapshot as the authoritative head commit for
          subsequent queries.
        """
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

            file_paths = [f.path for f in files if not should_ignore_path(Path(f.path))]
            chunks = self._index_semantic_snapshot(repo=repo, head_commit=head_commit, file_paths=file_paths)
            write_json(out_dir / "chunks.json", dump_chunks(chunks))
        except Exception as exc:  # noqa: BLE001
            return self.fail_index_run(run_id, error=str(exc))

        return self.complete_index_run(run_id, head_commit=head_commit)

    def _resolve_accepted_head_commit(self, repo: RepoRecord) -> str:
        repo_path = Path(repo.local_path)

        if repo.preferred_remote:
            try:
                fetch_remote(repo_path, repo.preferred_remote)
                return rev_parse(repo_path, f"refs/remotes/{repo.preferred_remote}/{repo.accepted_branch}")
            except Exception:  # noqa: BLE001
                pass

        return rev_parse(repo_path, f"refs/heads/{repo.accepted_branch}")

    def _load_snapshot_json(self, repo_id: str, head_commit: str) -> dict[str, Any]:
        return load_snapshot_artifacts(self._data_dir, repo_id, head_commit)

    def _write_snapshot(
        self,
        *,
        repo_id: str,
        head_commit: str,
        files: list[dict[str, Any]],
        symbols: list[dict[str, Any]],
        calls: list[dict[str, Any]],
    ) -> None:
        out_dir = repo_snapshot_dir(self._data_dir, repo_id, head_commit)
        write_json(out_dir / "files.json", files)
        write_json(out_dir / "symbols.json", symbols)
        write_json(out_dir / "calls.json", calls)

    def _index_semantic_for_paths(
        self,
        *,
        repo_id: str,
        head_commit: str,
        changed_paths: set[str],
        deleted_paths: set[str],
    ) -> None:
        repo = self.get_repo(repo_id)
        to_delete = sorted({p for p in changed_paths | deleted_paths if p})
        if to_delete:
            try:
                self._vector_store.delete_by_file_paths(repo_id=repo_id, file_paths=to_delete)
            except Exception:  # noqa: BLE001
                pass

        to_index = sorted({p for p in changed_paths if p})
        self._index_semantic_snapshot(repo=repo, head_commit=head_commit, file_paths=to_index)

    def update_repo_to_accepted_head_sync(self, repo_id: str, *, blocking: bool = True) -> IndexRunRecord:
        """Update repo artifacts to the latest accepted branch head.

        If the repo has never been indexed successfully, this performs a full index of the accepted head.

        This method is accepted-code-first: it ignores local working tree state and targets the accepted branch head.

        Why this exists:
        - The PRD requires incremental updates: when the accepted branch advances, CodeKnowl must update derived
          artifacts and semantic index data without requiring a full re-index every time.
        """

        repo = self.get_repo(repo_id)
        repo_path = Path(repo.local_path)

        lock = _get_update_lock(repo_id)
        acquired = lock.acquire(blocking=blocking)
        if not acquired:
            METRICS.inc("update.single_flight.skipped")
            latest = self.get_latest_successful_index_run_for_repo(repo_id)
            if latest:
                return latest
            raise ValueError("Repo update already in progress")

        run = self.start_index_run(repo_id)

        try:
            try:
                new_commit = self._resolve_accepted_head_commit(repo)
            except Exception as exc:  # noqa: BLE001
                return self.fail_index_run(run.run_id, error=str(exc))

            latest = self.get_latest_successful_index_run_for_repo(repo_id)
            old_commit = latest.head_commit if latest and latest.head_commit else None

            if old_commit == new_commit:
                return self.complete_index_run(run.run_id, head_commit=new_commit)

            try:
                if old_commit is None:
                    with TemporaryDirectory(prefix=f"codeknowl-wt-{repo_id[:8]}-") as td:
                        wt = Path(td)
                        worktree_add_detached(repo_path, wt, new_commit)
                        try:
                            files = dump_dataclasses(build_file_inventory(wt))
                            symbols_dc, calls_dc = extract_symbols_and_calls(wt)
                            symbols = dump_dataclasses(symbols_dc)
                            calls = dump_dataclasses(calls_dc)
                        finally:
                            worktree_remove(repo_path, wt)

                    self._write_snapshot(
                        repo_id=repo_id,
                        head_commit=new_commit,
                        files=files,
                        symbols=symbols,
                        calls=calls,
                    )
                    file_paths = [str(f.get("path")) for f in files if isinstance(f, dict) and f.get("path")]
                    chunks = self._index_semantic_snapshot(repo=repo, head_commit=new_commit, file_paths=file_paths)
                    out_dir = repo_snapshot_dir(self._data_dir, repo_id, new_commit)
                    write_json(out_dir / "chunks.json", dump_chunks(chunks))
                    return self.complete_index_run(run.run_id, head_commit=new_commit)

                delta = diff_name_status(repo_path, old_commit, new_commit)
                changed_paths: set[str] = {p for st, p in delta if st in {"A", "M"}}
                deleted_paths: set[str] = {p for st, p in delta if st == "D"}

                old_artifacts = self._load_snapshot_json(repo_id, old_commit)
                old_files: list[dict[str, Any]] = list(old_artifacts.get("files") or [])
                old_symbols: list[dict[str, Any]] = list(old_artifacts.get("symbols") or [])
                old_calls: list[dict[str, Any]] = list(old_artifacts.get("calls") or [])

                keep_files: dict[str, dict[str, Any]] = {
                    f.get("path"): f
                    for f in old_files
                    if isinstance(f, dict)
                    and f.get("path")
                    and f.get("path") not in deleted_paths
                    and f.get("path") not in changed_paths
                }

                keep_symbols = [
                    s
                    for s in old_symbols
                    if isinstance(s, dict)
                    and s.get("file_path")
                    and s.get("file_path") not in deleted_paths
                    and s.get("file_path") not in changed_paths
                ]

                keep_calls = [
                    c
                    for c in old_calls
                    if isinstance(c, dict)
                    and c.get("file_path")
                    and c.get("file_path") not in deleted_paths
                    and c.get("file_path") not in changed_paths
                ]

                with TemporaryDirectory(prefix=f"codeknowl-wt-{repo_id[:8]}-") as td:
                    wt = Path(td)
                    worktree_add_detached(repo_path, wt, new_commit)
                    try:
                        new_file_recs = dump_dataclasses(build_file_records_for_paths(wt, changed_paths))
                        new_syms_dc, new_calls_dc = extract_symbols_and_calls_for_paths(wt, changed_paths)
                        new_symbols = dump_dataclasses(new_syms_dc)
                        new_calls = dump_dataclasses(new_calls_dc)
                    finally:
                        worktree_remove(repo_path, wt)

                for f in new_file_recs:
                    p = f.get("path") if isinstance(f, dict) else None
                    if p:
                        keep_files[p] = f

                merged_files = sorted(keep_files.values(), key=lambda r: str(r.get("path")))
                merged_symbols = keep_symbols + new_symbols
                merged_calls = keep_calls + new_calls

                self._write_snapshot(
                    repo_id=repo_id,
                    head_commit=new_commit,
                    files=merged_files,
                    symbols=merged_symbols,
                    calls=merged_calls,
                )

                out_dir = repo_snapshot_dir(self._data_dir, repo_id, new_commit)
                old_chunks: list[dict[str, Any]] = list(old_artifacts.get("chunks") or [])
                keep_chunks = [
                    c
                    for c in old_chunks
                    if isinstance(c, dict)
                    and c.get("file_path")
                    and c.get("file_path") not in deleted_paths
                    and c.get("file_path") not in changed_paths
                ]

                self._index_semantic_for_paths(
                    repo_id=repo_id,
                    head_commit=new_commit,
                    changed_paths=changed_paths,
                    deleted_paths=deleted_paths,
                )

                with TemporaryDirectory(prefix=f"codeknowl-wt-chunks-{repo_id[:8]}-") as td:
                    wt = Path(td)
                    worktree_add_detached(repo_path, wt, new_commit)
                    try:
                        new_chunks = dump_chunks(
                            chunk_repo_files(
                                repo_id=repo_id,
                                head_commit=new_commit,
                                repo_path=wt,
                                file_paths=sorted(changed_paths),
                            )
                        )
                    finally:
                        worktree_remove(repo_path, wt)
                write_json(out_dir / "chunks.json", keep_chunks + new_chunks)

                return self.complete_index_run(run.run_id, head_commit=new_commit)
            except Exception as exc:  # noqa: BLE001
                return self.fail_index_run(run.run_id, error=str(exc))
        finally:
            lock.release()

    def repo_status(self, repo_id: str) -> dict[str, Any]:
        """Return the current status view for a repository.

        Why this exists:
        - IDE and operator workflows need a single endpoint/command to see the latest run status and the currently
          indexed head commit.
        """
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
        latest = self.get_latest_successful_index_run_for_repo(repo_id)
        if latest is None or not latest.head_commit:
            raise ValueError("Repo has no successful index run")
        return latest.head_commit

    def _load_latest_artifacts(self, repo_id: str) -> tuple[str, dict[str, Any]]:
        head_commit = self._get_latest_head_commit(repo_id)
        return head_commit, load_snapshot_artifacts(self._data_dir, repo_id, head_commit)

    def qa_where_is_symbol_defined(self, repo_id: str, symbol_name: str) -> dict[str, Any]:
        """Answer a deterministic "where is this symbol defined" question.

        Why this exists:
        - This supports IDE navigation and grounds answers in citations without requiring an LLM.
        """
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "where_is_symbol_defined", "symbol_name": symbol_name},
            "results": where_is_symbol_defined(artifacts, symbol_name),
        }

    def qa_what_calls_symbol_best_effort(self, repo_id: str, callee_name: str) -> dict[str, Any]:
        """Answer a best-effort "what calls this symbol" question.

        Why this exists:
        - This supports relationship navigation in the IDE and provides citations for call sites when available.
        """
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "what_calls_symbol", "callee_name": callee_name, "mode": "best_effort"},
            "results": find_callers_best_effort(artifacts, callee_name),
        }

    def qa_explain_file_stub(self, repo_id: str, file_path: str) -> dict[str, Any]:
        """Return a deterministic file explanation stub with citations.

        Why this exists:
        - The IDE needs a fast "explain this file" workflow; this provides a baseline answer grounded in extracted
          artifacts without requiring an LLM.
        """
        head_commit, artifacts = self._load_latest_artifacts(repo_id)
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "explain_file_stub", "file_path": file_path},
            "result": explain_file_stub(artifacts, file_path),
        }

    def qa_ask_llm(self, repo_id: str, question: str) -> dict[str, Any]:
        """Answer a free-form question using evidence retrieval and optional LLM synthesis.

        Why this exists:
        - This is the primary natural-language Q&A surface: retrieve evidence (semantic hits + structured artifacts)
          and produce an answer grounded in that evidence, optionally using multi-model synthesis.
        """
        head_commit, artifacts = self._load_latest_artifacts(repo_id)

        semantic_hits: list[dict[str, Any]] = []
        try:
            query_vector = self._embeddings.embed_texts([question])[0]
            hits = self._vector_store.search(
                repo_id=repo_id,
                head_commit=head_commit,
                query_vector=query_vector,
                limit=8,
            )
            semantic_hits = [
                {
                    "chunk_id": hit.chunk_id,
                    "score": hit.score,
                    "file_path": hit.file_path,
                    "start_line": hit.start_line,
                    "end_line": hit.end_line,
                    "text": hit.text,
                }
                for hit in hits
            ]
        except Exception:  # noqa: BLE001
            semantic_hits = []

        if self._reranker is not None and semantic_hits:
            try:
                documents = [str(semantic_hit.get("text") or "") for semantic_hit in semantic_hits]
                scores = self._reranker.rerank(query=question, documents=documents)
                if len(scores) == len(semantic_hits):
                    reranked_hits = []
                    for semantic_hit, score in zip(semantic_hits, scores, strict=True):
                        item = dict(semantic_hit)
                        item["rerank_score"] = float(score)
                        reranked_hits.append(item)
                    semantic_hits = sorted(
                        reranked_hits,
                        key=lambda x: float(x.get("rerank_score") or 0.0),
                        reverse=True,
                    )
            except Exception:  # noqa: BLE001
                pass

        profiles = LlmProfiles.from_env()
        if profiles is None:
            evidence, citations = build_evidence_bundle(artifacts, question, semantic_hits=semantic_hits)
            return {
                "repo_id": repo_id,
                "head_commit": head_commit,
                "query": {"type": "ask", "question": question, "mode": "deterministic_fallback"},
                "answer": "LLM is not configured. Returning best-effort evidence bundle only.",
                "citations": citations,
                "evidence": evidence,
            }

        coding_llm = OpenAiCompatibleClient(profiles.coding)
        general_llm = OpenAiCompatibleClient(profiles.general)
        synth_llm = OpenAiCompatibleClient(profiles.synth)

        result = answer_with_llm_synthesis(
            coding_llm=coding_llm,
            general_llm=general_llm,
            synth_llm=synth_llm,
            artifacts=artifacts,
            question=question,
            semantic_hits=semantic_hits,
        )
        return {
            "repo_id": repo_id,
            "head_commit": head_commit,
            "query": {"type": "ask", "question": question, "mode": "synthesis"},
            "answer": result.answer,
            "citations": result.citations,
            "evidence": result.evidence,
        }

    def _iter_text_files_for_search(self, repo_path: Path):
        for p in repo_path.rglob("*"):
            if not p.is_file():
                continue
            if should_ignore_path(p):
                continue
            try:
                data = p.read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:4096]:
                continue
            yield p, data

    def _find_line_occurrences(self, *, rel_path: str, text: str, needle: str) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for i, line in enumerate(text.splitlines(), start=1):
            if needle not in line:
                continue
            matches.append(
                {
                    "match": needle,
                    "line_preview": (line[:200] + "…") if len(line) > 200 else line,
                    "citation": {"file_path": rel_path, "start_line": i, "end_line": i},
                }
            )
        return matches

    def qa_find_occurrences(self, repo_id: str, needle: str, *, max_results: int = 200) -> dict[str, Any]:
        """Find text occurrences across repo files with citations.

        Why this exists:
        - Provides a deterministic fallback for "find occurrences" workflows when semantic or symbol-based queries are
          insufficient.
        """
        if not needle:
            raise ValueError("needle must not be empty")

        repo = self.get_repo(repo_id)
        repo_path = Path(repo.local_path)

        results: list[dict[str, Any]] = []
        for p, data in self._iter_text_files_for_search(repo_path):
            if len(results) >= max_results:
                break
            rel_path = str(p.relative_to(repo_path))
            text = data.decode("utf-8", errors="replace")
            results.extend(self._find_line_occurrences(rel_path=rel_path, text=text, needle=needle))
            if len(results) >= max_results:
                results = results[:max_results]
                break

        return {
            "repo_id": repo_id,
            "query": {"type": "find_occurrences", "needle": needle, "max_results": max_results},
            "results": results,
        }
