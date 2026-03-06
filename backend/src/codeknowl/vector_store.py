"""File: backend/src/codeknowl/vector_store.py
Purpose: Provide vector store operations for semantic retrieval (Qdrant primary; file fallback for OSS eval).
Product/business importance: Enables Milestone 3 semantic retrieval with traceable citations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from codeknowl.chunking import ChunkRecord


@dataclass(frozen=True)
class SemanticHit:
    chunk_id: str
    score: float
    file_path: str
    start_line: int
    end_line: int
    text: str


class VectorStore(Protocol):
    def upsert(self, *, repo_id: str, head_commit: str, chunks: list[ChunkRecord], vectors: list[list[float]]) -> None:
        raise NotImplementedError

    def delete_by_file_paths(self, *, repo_id: str, file_paths: list[str]) -> None:
        raise NotImplementedError

    def search(
        self, *, repo_id: str, head_commit: str, query_vector: list[float], limit: int = 8
    ) -> list[SemanticHit]:
        raise NotImplementedError


@dataclass(frozen=True)
class VectorStoreConfig:
    mode: str

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_VECTOR_") -> "VectorStoreConfig":
        mode = os.environ.get(f"{prefix}MODE", "qdrant").strip().lower()
        return VectorStoreConfig(mode=mode)


@dataclass(frozen=True)
class QdrantConfig:
    base_url: str
    api_key: str | None
    collection: str
    timeout_seconds: float

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_QDRANT_") -> "QdrantConfig":
        base_url = os.environ.get(f"{prefix}BASE_URL", "").rstrip("/")
        if not base_url:
            raise ValueError(f"Missing {prefix}BASE_URL")
        api_key = os.environ.get(f"{prefix}API_KEY")
        collection = os.environ.get(f"{prefix}COLLECTION", "codeknowl_chunks")
        timeout_seconds = float(os.environ.get(f"{prefix}TIMEOUT_SECONDS", "30"))
        return QdrantConfig(
            base_url=base_url,
            api_key=api_key,
            collection=collection,
            timeout_seconds=timeout_seconds,
        )


class QdrantVectorStore:
    def __init__(self, cfg: QdrantConfig):
        self._cfg = cfg

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._cfg.api_key:
            headers["api-key"] = self._cfg.api_key
        return headers

    def _ensure_collection(self, dim: int) -> None:
        url = f"{self._cfg.base_url}/collections/{self._cfg.collection}"
        with httpx.Client(timeout=self._cfg.timeout_seconds) as client:
            resp = client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return
            if resp.status_code != 404:
                resp.raise_for_status()

            payload = {
                "vectors": {"size": dim, "distance": "Cosine"},
            }
            create = client.put(url, headers=self._headers(), json=payload)
            create.raise_for_status()

    def upsert(self, *, repo_id: str, head_commit: str, chunks: list[ChunkRecord], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError("chunks/vectors length mismatch")

        self._ensure_collection(dim=len(vectors[0]))

        points = []
        for c, v in zip(chunks, vectors, strict=True):
            points.append(
                {
                    "id": c.chunk_id,
                    "vector": v,
                    "payload": {
                        "repo_id": repo_id,
                        "file_path": c.file_path,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "text": c.text,
                    },
                }
            )

        url = f"{self._cfg.base_url}/collections/{self._cfg.collection}/points?wait=true"
        with httpx.Client(timeout=self._cfg.timeout_seconds) as client:
            resp = client.put(url, headers=self._headers(), json={"points": points})
            resp.raise_for_status()

    def delete_by_file_paths(self, *, repo_id: str, file_paths: list[str]) -> None:
        if not file_paths:
            return

        url = f"{self._cfg.base_url}/collections/{self._cfg.collection}/points/delete?wait=true"
        with httpx.Client(timeout=self._cfg.timeout_seconds) as client:
            resp = client.post(
                url,
                headers=self._headers(),
                json={
                    "filter": {
                        "must": [
                            {"key": "repo_id", "match": {"value": repo_id}},
                            {"key": "file_path", "match": {"any": file_paths}},
                        ]
                    }
                },
            )
            resp.raise_for_status()

    def search(self, *, repo_id: str, head_commit: str, query_vector: list[float], limit: int = 8) -> list[SemanticHit]:
        url = f"{self._cfg.base_url}/collections/{self._cfg.collection}/points/search"
        with httpx.Client(timeout=self._cfg.timeout_seconds) as client:
            resp = client.post(
                url,
                headers=self._headers(),
                json={
                    "vector": query_vector,
                    "limit": limit,
                    "with_payload": True,
                    "filter": {
                        "must": [
                            {"key": "repo_id", "match": {"value": repo_id}},
                        ]
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result")
        if not isinstance(result, list):
            return []

        hits: list[SemanticHit] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            payload = item.get("payload") or {}
            hits.append(
                SemanticHit(
                    chunk_id=str(item.get("id")),
                    score=float(item.get("score") or 0.0),
                    file_path=str(payload.get("file_path") or ""),
                    start_line=int(payload.get("start_line") or 1),
                    end_line=int(payload.get("end_line") or 1),
                    text=str(payload.get("text") or ""),
                )
            )
        return hits


class FileVectorStore:
    def __init__(self, data_dir: Path):
        self._root = data_dir / "vector_store"
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, repo_id: str) -> Path:
        return self._root / f"{repo_id}.jsonl"

    def upsert(self, *, repo_id: str, head_commit: str, chunks: list[ChunkRecord], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError("chunks/vectors length mismatch")

        existing = {rec["chunk_id"]: rec for rec in self._load(repo_id)}
        for c, v in zip(chunks, vectors, strict=True):
            existing[c.chunk_id] = {
                "chunk_id": c.chunk_id,
                "repo_id": repo_id,
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "text": c.text,
                "vector": v,
            }

        path = self._path(repo_id)
        with path.open("w", encoding="utf-8") as f:
            for rec in existing.values():
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True))
                f.write("\n")

    def delete_by_file_paths(self, *, repo_id: str, file_paths: list[str]) -> None:
        if not file_paths:
            return
        file_paths_set = set(file_paths)
        kept = [rec for rec in self._load(repo_id) if rec.get("file_path") not in file_paths_set]
        path = self._path(repo_id)
        with path.open("w", encoding="utf-8") as f:
            for rec in kept:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True))
                f.write("\n")

    def search(self, *, repo_id: str, head_commit: str, query_vector: list[float], limit: int = 8) -> list[SemanticHit]:
        scored: list[tuple[float, dict[str, Any]]] = []
        for rec in self._load(repo_id):
            vec = rec.get("vector")
            if not isinstance(vec, list):
                continue
            score = _cosine_similarity(query_vector, [float(x) for x in vec])
            scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        hits: list[SemanticHit] = []
        for score, rec in scored[:limit]:
            hits.append(
                SemanticHit(
                    chunk_id=str(rec.get("chunk_id") or ""),
                    score=float(score),
                    file_path=str(rec.get("file_path") or ""),
                    start_line=int(rec.get("start_line") or 1),
                    end_line=int(rec.get("end_line") or 1),
                    text=str(rec.get("text") or ""),
                )
            )
        return hits

    def _load(self, repo_id: str) -> list[dict[str, Any]]:
        path = self._path(repo_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict) and rec.get("repo_id") == repo_id:
                    rows.append(rec)
        return rows


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def vector_store_from_env(*, data_dir: Path) -> VectorStore:
    cfg = VectorStoreConfig.from_env()
    if cfg.mode == "file":
        return FileVectorStore(data_dir)
    if cfg.mode == "qdrant":
        return QdrantVectorStore(QdrantConfig.from_env())
    raise ValueError(f"Unsupported vector store mode: {cfg.mode}")
