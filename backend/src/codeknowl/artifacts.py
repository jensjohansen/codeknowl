"""File: backend/src/codeknowl/artifacts.py
Purpose: Define artifact data structures and JSON read/write helpers for indexed snapshot outputs.
Product/business importance: Artifacts are the durable evidence boundary for citations and reproducibility in
Milestone 1 indexing.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceRange:
    """Zero-based source range for citations.

    Why this exists:
    - Citations need a stable way to point to specific spans within files for reproducibility.
    """

    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class Citation:
    """A file and range used as evidence in answers.

    Why this exists:
    - QA answers must include precise, reproducible evidence locations.
    """

    file_path: str
    range: SourceRange


@dataclass(frozen=True)
class FileRecord:
    """Metadata for a file included in a snapshot.

    Why this exists:
    - Indexing and QA need file metadata (path, language, size) without scanning the filesystem repeatedly.
    """

    path: str
    language: str
    size_bytes: int


@dataclass(frozen=True)
class SymbolRecord:
    """A definition or declaration extracted from source code.

    Why this exists:
    - IDE navigation and deterministic QA need to know where symbols are defined.
    """

    symbol_id: str
    kind: str
    name: str
    file_path: str
    range: SourceRange


@dataclass(frozen=True)
class CallRecord:
    """A call site extracted from source code.

    Why this exists:
    - Relationship navigation and deterministic QA need to know where calls occur.
    """

    caller_symbol_id: str
    callee_name: str
    file_path: str
    range: SourceRange


def artifacts_root(data_dir: Path) -> Path:
    """Return the root directory for all snapshot artifacts.

    Why this exists:
    - Indexing and QA need a single place to store and load snapshot JSON files.
    """
    return data_dir / "artifacts"


def repo_snapshot_dir(data_dir: Path, repo_id: str, head_commit: str) -> Path:
    """Return the directory for a specific repo snapshot.

    Why this exists:
    - Indexing and QA need a deterministic location for a repo’s snapshot JSON files.
    """
    return artifacts_root(data_dir) / repo_id / head_commit


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON file with stable formatting.

    Why this exists:
    - Snapshot artifacts must be deterministic and human-readable for debugging and reproducibility.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def dump_dataclasses(items: list[Any]) -> list[dict[str, Any]]:
    """Convert a list of dataclasses to JSON-serializable dicts.

    Why this exists:
    - Artifact JSON files need a simple way to serialize dataclass instances.
    """
    return [asdict(x) for x in items]
