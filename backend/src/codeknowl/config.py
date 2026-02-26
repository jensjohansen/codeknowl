from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path

    @staticmethod
    def default() -> "AppConfig":
        return AppConfig(data_dir=Path(".codeknowl"))
