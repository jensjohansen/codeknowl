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

    sub.add_parser("repo-list", help="List registered repositories")

    p_index = sub.add_parser("repo-index", help="Run an indexing job (synchronous for now)")
    p_index.add_argument("repo_id")

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

    p_ask = sub.add_parser("qa-ask", help="Ask a natural-language question (LLM + evidence bundle)")
    p_ask.add_argument("repo_id")
    p_ask.add_argument("question")

    args = parser.parse_args()

    service = CodeKnowlService(data_dir=Path(args.data_dir))

    if args.cmd == "repo-register":
        record = service.register_repo_local_path(Path(args.local_path))
        _print(
            {
                "repo_id": record.repo_id,
                "local_path": record.local_path,
                "created_at_utc": record.created_at_utc,
            }
        )
        return

    if args.cmd == "repo-list":
        repos = service.list_repos()
        _print(
            [
                {
                    "repo_id": r.repo_id,
                    "local_path": r.local_path,
                    "created_at_utc": r.created_at_utc,
                }
                for r in repos
            ]
        )
        return

    if args.cmd == "repo-index":
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
        return

    if args.cmd == "repo-status":
        _print(service.repo_status(args.repo_id))
        return

    if args.cmd == "qa-where-defined":
        _print(service.qa_where_is_symbol_defined(args.repo_id, args.symbol_name))
        return

    if args.cmd == "qa-what-calls":
        _print(service.qa_what_calls_symbol_best_effort(args.repo_id, args.callee_name))
        return

    if args.cmd == "qa-explain-file":
        _print(service.qa_explain_file_stub(args.repo_id, args.file_path))
        return

    if args.cmd == "qa-ask":
        _print(service.qa_ask_llm(args.repo_id, args.question))
        return

    raise RuntimeError(f"Unhandled command: {args.cmd}")
