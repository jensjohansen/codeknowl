"""
File: backend/src/codeknowl/app.py
Purpose: BlackSheep ASGI application and HTTP route definitions.
Product/business importance: Provides the HTTP API surface for CodeKnowl backend services.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from blacksheep import Application, Content, Response

from codeknowl.async_service import create_async_service
from codeknowl.audit import (
    audit,
    audit_fields_from_auth_context,
    audit_fields_from_request,
    hash_text,
)
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
from codeknowl.structured_logging import setup_structured_logging


def _json_response(data: object, *, status: int = 200) -> Response:
    """Serialize data to JSON and return a starlette Response.

    Why this exists:
    - HTTP endpoints need a consistent way to return JSON responses.
    """
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(status, None, Content(b"application/json", payload))


def _get_request_id(request) -> str | None:
    """Extract the request_id from the request object.

    Why this exists:
    - Audit logging needs to correlate logs with a request identifier.
    """
    return getattr(request, "request_id", None)


def _register_health_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    auth_enabled: bool,
    poll_interval_seconds: int | None,
) -> None:
    """Register health check endpoints.

    Why this exists:
    - Monitoring and load balancers need a health endpoint.
    """
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
    """Register Prometheus metrics endpoint.

    Why this exists:
    - Observability dashboards need Prometheus-compatible metrics.
    """
    def metrics() -> Response:
        content_type, data = METRICS.export()
        return Response(200, None, Content(content_type.encode(), data))

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
    """Enforce repo-scoped access control; return 403 if forbidden.

    Why this exists:
    - Repo routes must ensure the user has permission for the specific repo and operation.
    """
    auth_context = _get_auth_context(request)
    if auth_context is None:
        # Legacy API key mode: allow.
        return None
    if is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id=repo_id, op=op):
        return None
    return _json_response({"error": "forbidden"}, status=403)


def _register_repo_list_routes(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    """Register repo listing routes with optional RBAC filtering.

    Why this exists:
    - The IDE needs to list repos the user can access.
    """
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
    """Register repo registration route (admin-only).

    Why this exists:
    - The IDE needs to register new repositories for indexing.
    """
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


def _register_repo_index_routes(app: Application, service, *, group_config: GroupAuthzConfig) -> None:
    """Register repo indexing route (write access required).

    Why this exists:
    - The IDE needs to trigger (re)indexing of a repository.
    """
    async def index_repo(repo_id: str, request) -> Response:
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

        METRICS.inc_http_request("POST", "/repos/{repo_id}/index", 200)
        try:
            service.get_repo(repo_id)
        except KeyError:
            METRICS.inc_http_request("POST", "/repos/{repo_id}/index", 404)
            return _json_response({"error": "repo not found"}, status=404)
        
        # Enqueue async job instead of running synchronously
        job_id = await service.enqueue_index_job(repo_id)
        METRICS.inc_job_queued("index")
        METRICS.inc_http_request("POST", "/repos/{repo_id}/index", 202)

        audit().log(
            "repos.index.queued",
            fields={
                **audit_fields_from_request(request),
                **audit_fields_from_auth_context(_get_auth_context(request)),
                "request.id": _get_request_id(request),
                "repo.id": repo_id,
                "job.id": job_id,
            },
        )
        return _json_response(
            {
                "status": "queued",
                "job_id": job_id,
                "repo_id": repo_id,
            }
        )
    app.router.add_post("/repos/{repo_id}/index", index_repo)


def _register_repo_update_routes(
    app: Application,
    service,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    """Register repo update route (write access required).

    Why this exists:
    - The IDE needs to trigger accepted-code-first updates.
    """
    async def update_repo(repo_id: str, request) -> Response:
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

        METRICS.inc_http_request("POST", "/repos/{repo_id}/update", 200)
        try:
            service.get_repo(repo_id)
        except KeyError:
            METRICS.inc_http_request("POST", "/repos/{repo_id}/update", 404)
            return _json_response({"error": "repo not found"}, status=404)
        
        # Enqueue async job instead of running synchronously
        job_id = await service.enqueue_update_job(repo_id)
        METRICS.inc_job_queued("update")
        METRICS.inc_http_request("POST", "/repos/{repo_id}/update", 202)
        
        audit().log(
            "repos.update.queued",
            fields={
                **audit_fields_from_request(request),
                **audit_fields_from_auth_context(_get_auth_context(request)),
                "request.id": _get_request_id(request),
                "repo.id": repo_id,
                "job.id": job_id,
            },
        )
        
        return _json_response({
            "status": "queued",
            "job_id": job_id,
            "repo_id": repo_id,
        })
    
    app.router.add_post("/repos/{repo_id}/update", update_repo)


def _register_repo_status_routes(
    app: Application,
    service: CodeKnowlService,
    *,
    group_config: GroupAuthzConfig,
) -> None:
    """Register repo status route (read access required).

    Why this exists:
    - The IDE needs to display indexing and metadata status.
    """
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
    """Register repo deletion route (admin-only).

    Why this exists:
    - The IDE needs to offboard repositories.
    """
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
    """Register all repo-related routes.

    Why this exists:
    - Centralizes route registration for the repo API.
    """
    _register_repo_list_routes(app, service, group_config=group_config)
    _register_repo_register_routes(app, service, group_config=group_config)
    _register_repo_index_routes(app, service, group_config=group_config)
    _register_repo_update_routes(app, service, group_config=group_config)
    _register_repo_status_routes(app, service, group_config=group_config)
    _register_repo_delete_routes(app, service, group_config=group_config)


def _register_qa_where_defined(app: Application, service: CodeKnowlService, *, group_config: GroupAuthzConfig) -> None:
    """Register QA where-defined endpoint.

    Why this exists:
    - The IDE needs deterministic symbol definition answers.
    """
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
    """Register QA find-occurrences endpoint.

    Why this exists:
    - The IDE needs to locate all occurrences of a string in a repo.
    """
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
    """Register QA what-calls endpoint.

    Why this exists:
    - The IDE needs to find all callers of a symbol.
    """
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
    """Register QA explain-file endpoint.

    Why this exists:
    - The IDE needs a deterministic file summary without using an LLM.
    """
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
    """Register QA ask endpoint (LLM-backed answers).

    Why this exists:
    - The IDE needs to ask natural language questions with LLM-generated answers.
    """
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
    """Register all QA routes.

    Why this exists:
    - Centralizes route registration for the QA API.
    """
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
    """Extract and validate OIDC bearer token if present.

    Why this exists:
    - Enforces OIDC authentication when enabled.
    """
    authz = None
    try:
        authz = request.headers.get_first(b"authorization")
    except Exception:  # noqa: BLE001
        authz = None

    bearer = parse_bearer_token(authz.decode("utf-8", errors="replace") if authz else None)
    if not bearer:
        return None, _json_response({"error": "unauthorized"}, status=401)

    try:
        return oidc_verifier.verify_bearer_token(bearer), None
    except ValueError:
        return None, _json_response({"error": "unauthorized"}, status=401)


def _is_api_key_allowed(request, *, api_key: str | None) -> bool:
    """Check if an API key is allowed via environment allowlist.

    Why this exists:
    - Provides a simple API key allowlist for legacy/automation use.
    """
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
            return await handler(request)

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
        return await handler(request)

    return auth_middleware


def _configure_auth(app: Application):
    """Configure authentication and authorization from environment.

    Why this exists:
    - Enables OIDC and optional API key authentication.
    """
    api_key = os.environ.get("CODEKNOWL_API_KEY")
    oidc_config = OidcConfig.from_env(os.environ)
    group_config = GroupAuthzConfig.from_env(os.environ)
    oidc_verifier = OidcVerifier(config=oidc_config) if oidc_config else None

    auth_enabled = bool(api_key) or (oidc_verifier is not None)

    if auth_enabled:
        app.middlewares.append(_make_auth_middleware(api_key=api_key, oidc_verifier=oidc_verifier))

    return auth_enabled, group_config


async def create_app(config: AppConfig | None = None) -> Application:
    """Create the BlackSheep ASGI app for CodeKnowl backend.

    Why this exists:
    - Centralizes app creation and route registration.
    """
    configuration = config or AppConfig.default()
    
    # Setup structured logging
    setup_structured_logging()
    
    # Create async service with job queue
    async_service = await create_async_service(configuration.data_dir)
    
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

    _register_health_routes(app, async_service, auth_enabled=auth_enabled, poll_interval_seconds=interval)
    _register_metrics_routes(app)
    _register_repo_routes(app, async_service, group_config=group_config)
    _register_qa_routes(app, async_service, group_config=group_config)

    return app
