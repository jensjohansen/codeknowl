"""File: backend/src/codeknowl/app.py
Purpose: Define the CodeKnowl BlackSheep ASGI application and HTTP route wiring.
Product/business importance: This is the backend entrypoint that serves IDE and CLI-driven workflows for Milestone 1+.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

from pathlib import Path

from blacksheep import Application, Content
from blacksheep.messages import Response

from codeknowl.config import AppConfig
from codeknowl.service import CodeKnowlService


def _register_health_routes(app: Application) -> None:
    @app.get("/health")
    def health() -> Response:
        return Content({"status": "ok"})


def _register_repo_routes(app: Application, service: CodeKnowlService) -> None:
    @app.get("/repos")
    def list_repos() -> Response:
        repos = service.list_repos()
        return Content(
            [
                {
                    "repo_id": r.repo_id,
                    "local_path": r.local_path,
                    "created_at_utc": r.created_at_utc,
                }
                for r in repos
            ]
        )

    @app.post("/repos")
    async def register_repo(request) -> Response:
        payload = await request.json()
        local_path = payload.get("local_path")
        if not local_path:
            return Content({"error": "local_path is required"}, status=400)

        record = service.register_repo_local_path(Path(local_path))
        return Content(
            {
                "repo_id": record.repo_id,
                "local_path": record.local_path,
                "created_at_utc": record.created_at_utc,
            },
            status=201,
        )

    @app.post("/repos/{repo_id}/index")
    def index_repo(repo_id: str) -> Response:
        run = service.start_index_run(repo_id)
        completed = service.run_indexing_sync(run.run_id)
        return Content(
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

    @app.get("/repos/{repo_id}/status")
    def repo_status(repo_id: str) -> Response:
        try:
            status = service.repo_status(repo_id)
        except KeyError:
            return Content({"error": "repo not found"}, status=404)
        return Content(status)


def _register_qa_where_defined(app: Application, service: CodeKnowlService) -> None:
    @app.get("/repos/{repo_id}/qa/where-defined")
    def qa_where_defined(repo_id: str, name: str) -> Response:
        try:
            return Content(service.qa_where_is_symbol_defined(repo_id, name))
        except KeyError:
            return Content({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return Content({"error": str(exc)}, status=400)


def _register_qa_what_calls(app: Application, service: CodeKnowlService) -> None:

    @app.get("/repos/{repo_id}/qa/what-calls")
    def qa_what_calls(repo_id: str, callee: str) -> Response:
        try:
            return Content(service.qa_what_calls_symbol_best_effort(repo_id, callee))
        except KeyError:
            return Content({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return Content({"error": str(exc)}, status=400)


def _register_qa_explain_file(app: Application, service: CodeKnowlService) -> None:

    @app.get("/repos/{repo_id}/qa/explain-file")
    def qa_explain_file(repo_id: str, path: str) -> Response:
        try:
            return Content(service.qa_explain_file_stub(repo_id, path))
        except KeyError as exc:
            return Content({"error": str(exc)}, status=404)
        except ValueError as exc:
            return Content({"error": str(exc)}, status=400)


def _register_qa_ask(app: Application, service: CodeKnowlService) -> None:

    @app.post("/repos/{repo_id}/qa/ask")
    async def qa_ask(repo_id: str, request) -> Response:
        payload = await request.json()
        question = payload.get("question")
        if not question:
            return Content({"error": "question is required"}, status=400)

        try:
            return Content(service.qa_ask_llm(repo_id, question))
        except KeyError:
            return Content({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return Content({"error": str(exc)}, status=400)


def _register_qa_routes(app: Application, service: CodeKnowlService) -> None:
    _register_qa_where_defined(app, service)
    _register_qa_what_calls(app, service)
    _register_qa_explain_file(app, service)
    _register_qa_ask(app, service)


def create_app(config: AppConfig | None = None) -> Application:
    """Create the BlackSheep ASGI app for CodeKnowl backend."""
    cfg = config or AppConfig.default()
    service = CodeKnowlService(data_dir=cfg.data_dir)

    app = Application()

    _register_health_routes(app)
    _register_repo_routes(app, service)
    _register_qa_routes(app, service)

    return app
