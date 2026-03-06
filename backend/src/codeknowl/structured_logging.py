"""
File: backend/src/codeknowl/structured_logging.py
Purpose: Loki-compatible structured logging configuration.
Product/business importance: Enables Milestone 6 observability with Loki + Prometheus/Grafana.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class LokiFormatter(logging.Formatter):
    """Structured log formatter compatible with Loki.

    Why this exists:
    - Loki expects structured JSON logs with timestamp and level fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON for Loki.

        Why this exists:
        - Converts Python log records to structured JSON format.
        """
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "audit_event"):
            log_entry["audit"] = {
                "event": record.audit_event,
                "fields": getattr(record, "audit_fields", {}),
            }

        return json.dumps(log_entry)


def setup_structured_logging() -> None:
    """Configure structured logging for Loki compatibility.

    Why this exists:
    - Sets up root logger with JSON formatter for Loki ingestion.
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add structured JSON handler for stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(LokiFormatter())
    root_logger.addHandler(handler)


class AuditLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds audit context.

    Why this exists:
    - Provides structured audit logging with request context.
    """

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Add audit context to log record.

        Why this exists:
        - Ensures audit events have proper structured fields.
        """
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        
        # Add audit event and fields if provided
        if hasattr(self, "audit_event"):
            kwargs["extra"]["audit_event"] = self.audit_event
        if hasattr(self, "audit_fields"):
            kwargs["extra"]["audit_fields"] = self.audit_fields
        
        return msg, kwargs


def get_audit_logger(event: str, fields: dict[str, Any] | None = None) -> AuditLoggerAdapter:
    """Get an audit logger with event context.

    Why this exists:
    - Provides convenient way to log structured audit events.
    
    Args:
        event: Audit event name
        fields: Additional audit fields
        
    Returns:
        Logger adapter with audit context.
    """
    logger = logging.getLogger("codeknowl.audit")
    adapter = AuditLoggerAdapter(logger, {})
    adapter.audit_event = event
    adapter.audit_fields = fields or {}
    return adapter
