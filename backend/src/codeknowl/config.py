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
    data_dir: Path

    @staticmethod
    def default() -> "AppConfig":
        return AppConfig(data_dir=Path(".codeknowl"))
