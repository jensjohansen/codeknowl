from __future__ import annotations

from pathlib import Path

from blacksheep import Application, Content
from blacksheep.messages import Response

from codeknowl.config import AppConfig
from codeknowl.service import CodeKnowlService


def create_app(config: AppConfig | None = None) -> Application:
    cfg = config or AppConfig.default()
    service = CodeKnowlService(data_dir=cfg.data_dir)

    app = Application()

    @app.get("/health")
    def health() -> Response:
        return Content({"status": "ok"})

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

    return app
