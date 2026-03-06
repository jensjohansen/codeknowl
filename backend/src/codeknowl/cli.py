"""File: backend/src/codeknowl/cli.py
Purpose: Provide the `codeknowl` CLI for repo registration, indexing, status, and Milestone 1 Q&A commands.
Product/business importance: Enables local-first workflows and developer/operator testing without needing an IDE
extension.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codeknowl.config import AppConfig
from codeknowl.service import CodeKnowlService


def _print(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True))
    sys.stdout.write("\n")


def _cmd_repo_register(service: CodeKnowlService, args) -> None:
    record = service.register_repo_local_path(
        Path(args.local_path),
        accepted_branch=args.accepted_branch,
        preferred_remote=args.preferred_remote,
    )
    _print(
        {
            "repo_id": record.repo_id,
            "local_path": record.local_path,
            "accepted_branch": record.accepted_branch,
            "preferred_remote": record.preferred_remote,
            "created_at_utc": record.created_at_utc,
        }
    )


def _cmd_repo_update(service: CodeKnowlService, args) -> None:
    completed = service.update_repo_to_accepted_head_sync(args.repo_id)
    _print(
        {
            "run_id": completed.run_id,
            "repo_id": completed.repo_id,
            "status": completed.status,
            "started_at_utc": completed.started_at_utc,
            "finished_at_utc": completed.finished_at_utc,
            "error": completed.error,
            "head_commit": completed.head_commit,
        }
    )


def _cmd_repo_offboard(service: CodeKnowlService, args) -> None:
    try:
        service.offboard_repo(args.repo_id)
    except KeyError:
        _print({"error": "repo not found"})
        sys.exit(1)
    _print({"status": "deleted", "repo_id": args.repo_id})


def _cmd_repo_list(service: CodeKnowlService, _args) -> None:
    repos = service.list_repos()
    _print(
        [
            {
                "repo_id": r.repo_id,
                "local_path": r.local_path,
                "accepted_branch": r.accepted_branch,
                "preferred_remote": r.preferred_remote,
                "created_at_utc": r.created_at_utc,
            }
            for r in repos
        ]
    )


def _cmd_repo_index(service: CodeKnowlService, args) -> None:
    run = service.start_index_run(args.repo_id)
    completed = service.run_indexing_sync(run.run_id)
    _print(
        {
            "run_id": completed.run_id,
            "repo_id": completed.repo_id,
            "status": completed.status,
            "started_at_utc": completed.started_at_utc,
            "finished_at_utc": completed.finished_at_utc,
            "error": completed.error,
            "head_commit": completed.head_commit,
        }
    )


def _cmd_repo_status(service: CodeKnowlService, args) -> None:
    _print(service.repo_status(args.repo_id))


def _cmd_qa_where_defined(service: CodeKnowlService, args) -> None:
    _print(service.qa_where_is_symbol_defined(args.repo_id, args.symbol_name))


def _cmd_qa_what_calls(service: CodeKnowlService, args) -> None:
    _print(service.qa_what_calls_symbol_best_effort(args.repo_id, args.callee_name))


def _cmd_qa_explain_file(service: CodeKnowlService, args) -> None:
    _print(service.qa_explain_file_stub(args.repo_id, args.file_path))


def _cmd_qa_find_occurrences(service: CodeKnowlService, args) -> None:
    _print(service.qa_find_occurrences(args.repo_id, args.needle, max_results=args.max_results))


def _cmd_qa_ask(service: CodeKnowlService, args) -> None:
    _print(service.qa_ask_llm(args.repo_id, args.question))


def main() -> None:
    parser = argparse.ArgumentParser(prog="codeknowl")
    parser.add_argument(
        "--data-dir",
        default=str(AppConfig.default().data_dir),
        help="Directory used to store local state (SQLite). Default: .codeknowl",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("repo-register", help="Register a local repository path")
    p_register.add_argument("local_path", help="Local filesystem path to a git repository")
    p_register.add_argument(
        "accepted_branch",
        help="Accepted branch to monitor (exactly one; e.g. main/master/trunk)",
    )
    p_register.add_argument(
        "--preferred-remote",
        default=None,
        help="Preferred remote name (e.g. origin). If omitted, CodeKnowl will track the local branch head.",
    )

    sub.add_parser("repo-list", help="List registered repositories")

    p_offboard = sub.add_parser("repo-offboard", help="Remove a repository so it is no longer queryable")
    p_offboard.add_argument("repo_id")

    p_index = sub.add_parser("repo-index", help="Run an indexing job (synchronous for now)")
    p_index.add_argument("repo_id")

    p_update = sub.add_parser("repo-update", help="Update indexes to the latest accepted branch head")
    p_update.add_argument("repo_id")

    p_status = sub.add_parser("repo-status", help="Show repo status and latest index run")
    p_status.add_argument("repo_id")

    p_where = sub.add_parser("qa-where-defined", help="Where is a symbol defined? (artifact-backed)")
    p_where.add_argument("repo_id")
    p_where.add_argument("symbol_name")

    p_calls = sub.add_parser("qa-what-calls", help="What calls a symbol? (best-effort heuristic)")
    p_calls.add_argument("repo_id")
    p_calls.add_argument("callee_name")

    p_explain = sub.add_parser("qa-explain-file", help="Explain a file/module (deterministic stub)")
    p_explain.add_argument("repo_id")
    p_explain.add_argument("file_path", help="Repo-relative file path")

    p_occ = sub.add_parser("qa-find-occurrences", help="Find occurrences of a string in the repo (best-effort)")
    p_occ.add_argument("repo_id")
    p_occ.add_argument("needle")
    p_occ.add_argument("--max-results", type=int, default=200)

    p_ask = sub.add_parser("qa-ask", help="Ask a natural-language question (LLM + evidence bundle)")
    p_ask.add_argument("repo_id")
    p_ask.add_argument("question")

    args = parser.parse_args()

    service = CodeKnowlService(data_dir=Path(args.data_dir))

    dispatch = {
        "repo-register": _cmd_repo_register,
        "repo-list": _cmd_repo_list,
        "repo-offboard": _cmd_repo_offboard,
        "repo-index": _cmd_repo_index,
        "repo-update": _cmd_repo_update,
        "repo-status": _cmd_repo_status,
        "qa-where-defined": _cmd_qa_where_defined,
        "qa-what-calls": _cmd_qa_what_calls,
        "qa-explain-file": _cmd_qa_explain_file,
        "qa-find-occurrences": _cmd_qa_find_occurrences,
        "qa-ask": _cmd_qa_ask,
    }

    handler = dispatch.get(args.cmd)
    if handler is None:
        raise RuntimeError(f"Unhandled command: {args.cmd}")
    handler(service, args)
