"""File: backend/src/codeknowl/audit.py
Purpose: Provide lightweight structured audit logging for security-relevant actions.
Product/business importance: Supports Milestone 4 hardening and operator audit requirements.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(v: object, *, max_len: int = 256) -> str | None:
    if v is None:
        return None
    try:
        s = str(v)
    except Exception:  # noqa: BLE001
        return None
    s = s.replace("\n", " ").replace("\r", " ")
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def hash_text(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        return None


@dataclass(frozen=True)
class AuditConfig:
    enabled: bool
    sink: str
    file_path: Path | None
    include_query_text: bool

    @staticmethod
    def from_env(env: dict[str, str]) -> "AuditConfig":
        enabled_raw = env.get("CODEKNOWL_AUDIT_ENABLED", "true").strip().lower()
        enabled = enabled_raw not in {"0", "false", "no", "off"}

        sink = env.get("CODEKNOWL_AUDIT_SINK", "stdout").strip().lower()
        if sink not in {"stdout", "file"}:
            sink = "stdout"

        file_path = None
        if sink == "file":
            fp = env.get("CODEKNOWL_AUDIT_FILE", "").strip()
            file_path = Path(fp) if fp else Path(".codeknowl") / "audit.log"

        include_query_raw = env.get("CODEKNOWL_AUDIT_INCLUDE_QUERY_TEXT", "false").strip().lower()
        include_query_text = include_query_raw in {"1", "true", "yes", "on"}

        return AuditConfig(
            enabled=enabled,
            sink=sink,
            file_path=file_path,
            include_query_text=include_query_text,
        )


class AuditLogger:
    def __init__(self, config: AuditConfig):
        self._config = config
        self._logger = logging.getLogger("codeknowl.audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if self._logger.handlers:
            return

        if config.sink == "file":
            path = config.file_path or (Path(".codeknowl") / "audit.log")
            path.parent.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = logging.FileHandler(path, encoding="utf-8")
        else:
            handler = logging.StreamHandler()

        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def enabled(self) -> bool:
        return self._config.enabled

    def include_query_text(self) -> bool:
        return self._config.include_query_text

    def new_request_id(self) -> str:
        return str(uuid.uuid4())

    def log(self, event: str, *, fields: dict[str, Any] | None = None) -> None:
        if not self._config.enabled:
            return

        payload: dict[str, Any] = {
            "ts": _utc_now_iso(),
            "event": event,
        }
        if fields:
            payload.update({k: v for k, v in fields.items() if v is not None})

        try:
            self._logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            # Audit logging must never break request handling.
            return


_AUDIT = AuditLogger(AuditConfig.from_env(os.environ))


def audit() -> AuditLogger:
    return _AUDIT


def audit_fields_from_request(request) -> dict[str, Any]:
    """Best-effort extraction of request metadata.

    Avoids logging secrets (e.g., Authorization header contents).
    """

    headers = getattr(request, "headers", None)

    user_agent = None
    x_forwarded_for = None
    if headers is not None:
        try:
            user_agent_header = headers.get_first(b"user-agent")
            user_agent = user_agent_header.decode("utf-8", errors="replace") if user_agent_header else None
        except Exception:  # noqa: BLE001
            user_agent = None
        try:
            forwarded_for_header = headers.get_first(b"x-forwarded-for")
            x_forwarded_for = (
                forwarded_for_header.decode("utf-8", errors="replace") if forwarded_for_header else None
            )
        except Exception:  # noqa: BLE001
            x_forwarded_for = None

    path = _safe_str(getattr(request, "path", None), max_len=512)
    method = _safe_str(getattr(request, "method", None), max_len=16)

    return {
        "http.method": method,
        "http.path": path,
        "http.user_agent": _safe_str(user_agent, max_len=256),
        "http.x_forwarded_for": _safe_str(x_forwarded_for, max_len=256),
    }


def audit_fields_from_auth_context(auth_context: object | None) -> dict[str, Any]:
    if auth_context is None:
        return {
            "auth.subject": None,
            "auth.username": None,
            "auth.mode": "api_key_or_anonymous",
        }

    subject = _safe_str(getattr(auth_context, "subject", None), max_len=128)
    username = _safe_str(getattr(auth_context, "username", None), max_len=128)
    return {
        "auth.subject": subject,
        "auth.username": username,
        "auth.mode": "oidc",
    }
