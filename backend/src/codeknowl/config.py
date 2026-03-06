"""File: backend/src/codeknowl/config.py
Purpose: Define backend configuration structures and defaults.
Product/business importance: Centralizes configuration so deployments can be local-first and environment-driven.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Holds runtime configuration for the backend.

    Why this exists:
    - Callers (CLI and API server bootstrap) need a single, explicit object that controls where CodeKnowl stores
      its local-first state (SQLite + artifacts).
    """

    data_dir: Path

    @staticmethod
    def default() -> "AppConfig":
        """Return the default configuration used by local-first development.

        Why this exists:
        - Provides a predictable default (`.codeknowl`) so operators and developers can run the system without
          supplying configuration flags.
        """
        return AppConfig(data_dir=Path(".codeknowl"))
