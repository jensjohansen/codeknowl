"""File: backend/src/codeknowl/chunking.py
Purpose: Produce stable, citation-friendly text chunks from repository files for semantic indexing.
Product/business importance: Enables Milestone 3 semantic retrieval with traceable citations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    text: str


def dump_chunks(chunks: list[ChunkRecord]) -> list[dict[str, Any]]:
    return [asdict(c) for c in chunks]


def _hash_chunk_id(*, repo_id: str, file_path: str, start_line: int, end_line: int) -> str:
    raw = f"{repo_id}:{file_path}:{start_line}:{end_line}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def chunk_file_text(
    *,
    repo_id: str,
    head_commit: str,
    file_path: str,
    text: str,
    max_lines: int = 200,
    overlap_lines: int = 20,
) -> list[ChunkRecord]:
    lines = text.splitlines()
    if not lines:
        return []

    if max_lines <= 0:
        raise ValueError("max_lines must be > 0")
    if overlap_lines < 0:
        raise ValueError("overlap_lines must be >= 0")
    if overlap_lines >= max_lines:
        raise ValueError("overlap_lines must be < max_lines")

    chunks: list[ChunkRecord] = []
    i = 0
    while i < len(lines):
        start = i
        end = min(i + max_lines, len(lines))
        start_line = start + 1
        end_line = end
        chunk_text = "\n".join(lines[start:end]).strip()
        if chunk_text:
            chunk_id = _hash_chunk_id(
                repo_id=repo_id,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
            )
            chunks.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    text=chunk_text,
                )
            )

        if end >= len(lines):
            break
        i = end - overlap_lines

    return chunks


def chunk_repo_files(
    *,
    repo_id: str,
    head_commit: str,
    repo_path: Path,
    file_paths: list[str],
    max_bytes_per_file: int = 512_000,
) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []

    for rel in file_paths:
        abs_path = repo_path / rel
        try:
            if not abs_path.is_file():
                continue
            if abs_path.stat().st_size > max_bytes_per_file:
                continue
            text = abs_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        chunks.extend(
            chunk_file_text(
                repo_id=repo_id,
                head_commit=head_commit,
                file_path=rel,
                text=text,
            )
        )

    return chunks
