from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceRange:
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class Citation:
    file_path: str
    range: SourceRange


@dataclass(frozen=True)
class FileRecord:
    path: str
    language: str
    size_bytes: int


@dataclass(frozen=True)
class SymbolRecord:
    symbol_id: str
    kind: str
    name: str
    file_path: str
    range: SourceRange


@dataclass(frozen=True)
class CallRecord:
    caller_symbol_id: str
    callee_name: str
    file_path: str
    range: SourceRange


def artifacts_root(data_dir: Path) -> Path:
    return data_dir / "artifacts"


def repo_snapshot_dir(data_dir: Path, repo_id: str, head_commit: str) -> Path:
    return artifacts_root(data_dir) / repo_id / head_commit


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def dump_dataclasses(items: list[Any]) -> list[dict[str, Any]]:
    return [asdict(x) for x in items]
