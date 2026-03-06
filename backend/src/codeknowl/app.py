"""File: backend/src/codeknowl/app.py
Purpose: Define the CodeKnowl BlackSheep ASGI application and HTTP route wiring.
Product/business importance: This is the backend entrypoint that serves IDE and CLI-driven workflows for Milestone 1+.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json as pyjson
import os
from pathlib import Path

from blacksheep import Application, Content
from blacksheep.messages import Response
from blacksheep.server.normalization import ensure_response

from codeknowl.audit import audit, audit_fields_from_auth_context, audit_fields_from_request, hash_text
from codeknowl.auth import (
    GroupAuthzConfig,
    OidcConfig,
    OidcVerifier,
    is_admin,
    is_allowed_for_repo,
    parse_bearer_token,
)
from codeknowl.config import AppConfig
from codeknowl.metrics import METRICS
from codeknowl.poller import start_repo_poller
from codeknowl.service import CodeKnowlService


def _json_response(data: object, *, status: int = 200) -> Response:
    payload = pyjson.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(status, None, Content(b"application/json", payload))


def _get_request_id(request) -> str | None:
    return getattr(request, "request_id", None)


def _register_health_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    auth_enabled: bool,
    poll_interval_seconds: int | None,
) -> None:
    def health() -> Response:
        return _json_response(
            {
                "status": "ok",
                "details": {
                    "repo_count": len(service.list_repos()),
                    "auth_enabled": auth_enabled,
                    "poll_interval_seconds": poll_interval_seconds,
                },
            }
        )

    app.router.add_get("/health", health)


def _register_metrics_routes(app: Application) -> None:
    def metrics() -> Response:
        counters = METRICS.snapshot()
        index_attempt = counters.get("http.repos.index.attempt", 0)
        index_succeeded = counters.get("http.repos.index.succeeded", 0)
        update_attempt = counters.get("http.repos.update.attempt", 0)
        update_succeeded = counters.get("http.repos.update.succeeded", 0)

        index_success_rate = (index_succeeded / index_attempt) if index_attempt else None
        update_success_rate = (update_succeeded / update_attempt) if update_attempt else None

        return _json_response(
            {
                "counters": counters,
                "derived": {
                    "http.repos.index.success_rate": index_success_rate,
                    "http.repos.update.success_rate": update_success_rate,
                },
            }
        )

    app.router.add_get("/metrics", metrics)


def _get_auth_context(request):
    return getattr(request, "auth", None)


def _require_admin(request, *, group_config: GroupAuthzConfig) -> Response | None:
    auth_context = _get_auth_context(request)
    if auth_context is None:
        # Legacy API key mode: allow.
        return None
    if is_admin(group_config=group_config, auth_context=auth_context):
        return None
    return _json_response({"error": "forbidden"}, status=403)


def _require_repo_access(request, *, group_config: GroupAuthzConfig, repo_id: str, op: str) -> Response | None:
    auth_context = _get_auth_context(request)
    if auth_context is None:
        # Legacy API key mode: allow.
        return None
    if is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id=repo_id, op=op):
        return None
    return _json_response({"error": "forbidden"}, status=403)


def _register_repo_list_routes(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    def list_repos(request) -> Response:
        repos = service.list_repos()
        auth_context = _get_auth_context(request)
        if auth_context is not None:
            repos = [
                r
                for r in repos
                if is_allowed_for_repo(
                    group_config=group_config,
                    auth_context=auth_context,
                    repo_id=r.repo_id,
                    op="read",
                )
            ]

        return _json_response(
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

    app.router.add_get("/repos", list_repos)


def _register_repo_register_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    async def register_repo(request) -> Response:
        forbidden = _require_admin(request, group_config=group_config)
        if forbidden is not None:
            audit().log(
                "repos.register.forbidden",
                fields={
                    **audit_fields_from_request(request),
                    **audit_fields_from_auth_context(_get_auth_context(request)),
                    "request.id": _get_request_id(request),
                },
            )
            return forbidden

        payload = await request.json()
        local_path = payload.get("local_path")
        if not local_path:
            return _json_response({"error": "local_path is required"}, status=400)

        accepted_branch = payload.get("accepted_branch")
        if not accepted_branch:
            return _json_response({"error": "accepted_branch is required"}, status=400)

        preferred_remote = payload.get("preferred_remote")

        record = service.register_repo_local_path(
            Path(local_path),
            accepted_branch=accepted_branch,
            preferred_remote=preferred_remote,
        )

        audit().log(
            "repos.register.succeeded",
            fields={
                **audit_fields_from_request(request),
                **audit_fields_from_auth_context(_get_auth_context(request)),
                "request.id": _get_request_id(request),
                "repo.id": record.repo_id,
                "repo.accepted_branch": record.accepted_branch,
            },
        )
        return _json_response(
            {
                "repo_id": record.repo_id,
                "local_path": record.local_path,
                "accepted_branch": record.accepted_branch,
                "preferred_remote": record.preferred_remote,
                "created_at_utc": record.created_at_utc,
            },
            status=201,
        )

    app.router.add_post("/repos", register_repo)


def _register_repo_index_routes(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    def index_repo(repo_id: str, request) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="write")
        if forbidden is not None:
            audit().log(
                "repos.index.forbidden",
                fields={
                    **audit_fields_from_request(request),
                    **audit_fields_from_auth_context(_get_auth_context(request)),
                    "request.id": _get_request_id(request),
                    "repo.id": repo_id,
                },
            )
            return forbidden

        METRICS.inc("http.repos.index.attempt")
        try:
            service.get_repo(repo_id)
        except KeyError:
            METRICS.inc("http.repos.index.not_found")
            return _json_response({"error": "repo not found"}, status=404)
        run = service.start_index_run(repo_id)
        completed = service.run_indexing_sync(run.run_id)
        if completed.status == "succeeded":
            METRICS.inc("http.repos.index.succeeded")
        else:
            METRICS.inc("http.repos.index.failed")

        audit().log(
            "repos.index.completed",
            fields={
                **audit_fields_from_request(request),
                **audit_fields_from_auth_context(_get_auth_context(request)),
                "request.id": _get_request_id(request),
                "repo.id": repo_id,
                "run.id": completed.run_id,
                "run.status": completed.status,
                "run.head_commit": completed.head_commit,
            },
        )
        return _json_response(
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

    app.router.add_post("/repos/{repo_id}/index", index_repo)


def _register_repo_update_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    def update_repo(repo_id: str, request) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="write")
        if forbidden is not None:
            audit().log(
                "repos.update.forbidden",
                fields={
                    **audit_fields_from_request(request),
                    **audit_fields_from_auth_context(_get_auth_context(request)),
                    "request.id": _get_request_id(request),
                    "repo.id": repo_id,
                },
            )
            return forbidden

        METRICS.inc("http.repos.update.attempt")
        try:
            completed = service.update_repo_to_accepted_head_sync(repo_id)
        except KeyError:
            METRICS.inc("http.repos.update.not_found")
            return _json_response({"error": "repo not found"}, status=404)
        if completed.status == "succeeded":
            METRICS.inc("http.repos.update.succeeded")
        else:
            METRICS.inc("http.repos.update.failed")

        audit().log(
            "repos.update.completed",
            fields={
                **audit_fields_from_request(request),
                **audit_fields_from_auth_context(_get_auth_context(request)),
                "request.id": _get_request_id(request),
                "repo.id": repo_id,
                "run.id": completed.run_id,
                "run.status": completed.status,
                "run.head_commit": completed.head_commit,
            },
        )
        return _json_response(
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

    app.router.add_post("/repos/{repo_id}/update", update_repo)


def _register_repo_status_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    def repo_status(repo_id: str, request) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="read")
        if forbidden is not None:
            return forbidden

        try:
            status = service.repo_status(repo_id)
        except KeyError:
            return _json_response({"error": "repo not found"}, status=404)
        return _json_response(status)

    app.router.add_get("/repos/{repo_id}/status", repo_status)


def _register_repo_delete_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    def delete_repo(repo_id: str, request) -> Response:
        forbidden = _require_admin(request, group_config=group_config)
        if forbidden is not None:
            audit().log(
                "repos.delete.forbidden",
                fields={
                    **audit_fields_from_request(request),
                    **audit_fields_from_auth_context(_get_auth_context(request)),
                    "request.id": _get_request_id(request),
                    "repo.id": repo_id,
                },
            )
            return forbidden

        try:
            service.offboard_repo(repo_id)
        except KeyError:
            return _json_response({"error": "repo not found"}, status=404)

        audit().log(
            "repos.delete.succeeded",
            fields={
                **audit_fields_from_request(request),
                **audit_fields_from_auth_context(_get_auth_context(request)),
                "request.id": _get_request_id(request),
                "repo.id": repo_id,
            },
        )
        return _json_response({"status": "deleted", "repo_id": repo_id})

    app.router.add_delete("/repos/{repo_id}", delete_repo)


def _register_repo_routes(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    _register_repo_list_routes(app, service, group_config=group_config)
    _register_repo_register_routes(app, service, group_config=group_config)
    _register_repo_index_routes(app, service, group_config=group_config)
    _register_repo_update_routes(app, service, group_config=group_config)
    _register_repo_status_routes(app, service, group_config=group_config)
    _register_repo_delete_routes(app, service, group_config=group_config)


def _register_qa_where_defined(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    def qa_where_defined(repo_id: str, name: str, request, *, group_config: GroupAuthzConfig) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="read")
        if forbidden is not None:
            return forbidden

        try:
            return _json_response(service.qa_where_is_symbol_defined(repo_id, name))
        except KeyError:
            return _json_response({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return _json_response({"error": str(exc)}, status=400)

    app.router.add_get(
        "/repos/{repo_id}/qa/where-defined",
        lambda repo_id, name, request: qa_where_defined(repo_id, name, request, group_config=group_config),
    )


def _register_qa_find_occurrences(
    app: Application,
    service: CodeKnowlService,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    def qa_find_occurrences(
        repo_id: str,
        needle: str,
        request,
        *,
        group_config: GroupAuthzConfig,
        max_results: int = 200,
    ) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="read")
        if forbidden is not None:
            return forbidden

        try:
            return _json_response(service.qa_find_occurrences(repo_id, needle, max_results=max_results))
        except KeyError:
            return _json_response({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return _json_response({"error": str(exc)}, status=400)

    app.router.add_get(
        "/repos/{repo_id}/qa/find-occurrences",
        lambda repo_id, needle, request, max_results=200: qa_find_occurrences(
            repo_id,
            needle,
            request,
            group_config=group_config,
            max_results=max_results,
        ),
    )


def _register_qa_what_calls(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    def qa_what_calls(repo_id: str, callee: str, request, *, group_config: GroupAuthzConfig) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="read")
        if forbidden is not None:
            return forbidden

        try:
            return _json_response(service.qa_what_calls_symbol_best_effort(repo_id, callee))
        except KeyError:
            return _json_response({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return _json_response({"error": str(exc)}, status=400)

    app.router.add_get(
        "/repos/{repo_id}/qa/what-calls",
        lambda repo_id, callee, request: qa_what_calls(repo_id, callee, request, group_config=group_config),
    )


def _register_qa_explain_file(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    def qa_explain_file(repo_id: str, path: str, request, *, group_config: GroupAuthzConfig) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="read")
        if forbidden is not None:
            return forbidden

        try:
            return _json_response(service.qa_explain_file_stub(repo_id, path))
        except KeyError as exc:
            return _json_response({"error": str(exc)}, status=404)
        except ValueError as exc:
            return _json_response({"error": str(exc)}, status=400)

    app.router.add_get(
        "/repos/{repo_id}/qa/explain-file",
        lambda repo_id, path, request: qa_explain_file(repo_id, path, request, group_config=group_config),
    )


def _register_qa_ask(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    async def qa_ask(repo_id: str, request) -> Response:
        forbidden = _require_repo_access(request, group_config=group_config, repo_id=repo_id, op="read")
        if forbidden is not None:
            audit().log(
                "qa.ask.forbidden",
                fields={
                    **audit_fields_from_request(request),
                    **audit_fields_from_auth_context(_get_auth_context(request)),
                    "request.id": _get_request_id(request),
                    "repo.id": repo_id,
                },
            )
            return forbidden

        payload = await request.json()
        question = payload.get("question")
        if not question:
            return _json_response({"error": "question is required"}, status=400)

        audit_fields = {
            **audit_fields_from_request(request),
            **audit_fields_from_auth_context(_get_auth_context(request)),
            "request.id": _get_request_id(request),
            "repo.id": repo_id,
            "qa.question.sha256_16": hash_text(str(question)),
        }
        if audit().include_query_text():
            audit_fields["qa.question"] = str(question)
        audit().log("qa.ask.started", fields=audit_fields)

        try:
            response = service.qa_ask_llm(repo_id, question)
            audit().log(
                "qa.ask.succeeded",
                fields={
                    **audit_fields_from_request(request),
                    **audit_fields_from_auth_context(_get_auth_context(request)),
                    "request.id": _get_request_id(request),
                    "repo.id": repo_id,
                    "qa.question.sha256_16": hash_text(str(question)),
                },
            )
            return _json_response(response)
        except KeyError:
            return _json_response({"error": "repo not found"}, status=404)
        except ValueError as exc:
            return _json_response({"error": str(exc)}, status=400)

    app.router.add_post("/repos/{repo_id}/qa/ask", qa_ask)


def _register_qa_routes(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    _register_qa_where_defined(app, service, group_config=group_config)
    _register_qa_what_calls(app, service, group_config=group_config)
    _register_qa_explain_file(app, service, group_config=group_config)
    _register_qa_find_occurrences(app, service, group_config=group_config)
    _register_qa_ask(app, service, group_config=group_config)


def _maybe_get_oidc_auth_context(
    request,
    *,
    oidc_verifier: OidcVerifier | None,
) -> tuple[object | None, Response | None]:
    if oidc_verifier is None:
        return None, None

    authz = None
    try:
        authz = request.headers.get_first(b"authorization")
    except Exception:  # noqa: BLE001
        authz = None

    bearer = parse_bearer_token(authz.decode("utf-8", errors="replace") if authz else None)
    if not bearer:
        return None, None

    try:
        return oidc_verifier.verify_bearer_token(bearer), None
    except ValueError:
        return None, _json_response({"error": "unauthorized"}, status=401)


def _is_api_key_allowed(request, *, api_key: str | None) -> bool:
    if not api_key:
        return False

    provided = None
    try:
        provided = request.headers.get_first(b"x-codeknowl-api-key")
    except Exception:  # noqa: BLE001
        provided = None

    return bool(provided and provided.decode("utf-8", errors="replace") == api_key)


def _make_auth_middleware(*, api_key: str | None, oidc_verifier: OidcVerifier | None):
    async def auth_middleware(request, handler):
        if _get_request_id(request) is None:
            request.request_id = audit().new_request_id()

        path = getattr(request, "path", None)
        if path in {"/health", "/metrics"}:
            return ensure_response(await handler(request))

        auth_context, unauthorized = _maybe_get_oidc_auth_context(request, oidc_verifier=oidc_verifier)
        if unauthorized is not None:
            audit().log(
                "http.unauthorized",
                fields={
                    **audit_fields_from_request(request),
                    "request.id": _get_request_id(request),
                },
            )
            return unauthorized

        if auth_context is None and api_key and not _is_api_key_allowed(request, api_key=api_key):
            audit().log(
                "http.unauthorized",
                fields={
                    **audit_fields_from_request(request),
                    "request.id": _get_request_id(request),
                },
            )
            return _json_response({"error": "unauthorized"}, status=401)

        if auth_context is None and not api_key:
            audit().log(
                "http.unauthorized",
                fields={
                    **audit_fields_from_request(request),
                    "request.id": _get_request_id(request),
                },
            )
            return _json_response({"error": "unauthorized"}, status=401)

        request.auth = auth_context
        return ensure_response(await handler(request))

    return auth_middleware


def _configure_auth(app: Application):
    api_key = os.environ.get("CODEKNOWL_API_KEY")
    oidc_config = OidcConfig.from_env(os.environ)
    group_config = GroupAuthzConfig.from_env(os.environ)
    oidc_verifier = OidcVerifier(config=oidc_config) if oidc_config else None

    auth_enabled = bool(api_key) or (oidc_verifier is not None)

    if auth_enabled:
        app.middlewares.append(_make_auth_middleware(api_key=api_key, oidc_verifier=oidc_verifier))

    return auth_enabled, group_config


def create_app(config: AppConfig | None = None) -> Application:
    """Create the BlackSheep ASGI app for CodeKnowl backend."""
    configuration = config or AppConfig.default()
    service = CodeKnowlService(data_dir=configuration.data_dir)

    app = Application()

    auth_enabled, group_config = _configure_auth(app)

    poll_raw = os.environ.get("CODEKNOWL_POLL_INTERVAL_SECONDS")
    interval: int | None = None
    if poll_raw:
        try:
            interval = int(poll_raw)
        except ValueError:
            interval = 0
        if interval <= 0:
            interval = None
        else:
            start_repo_poller(data_dir=configuration.data_dir, interval_seconds=interval)

    _register_health_routes(app, service, auth_enabled=auth_enabled, poll_interval_seconds=interval)
    _register_metrics_routes(app)
    _register_repo_routes(app, service, group_config=group_config)
    _register_qa_routes(app, service, group_config=group_config)

    return app
