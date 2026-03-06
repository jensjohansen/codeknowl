"""File: backend/src/codeknowl/embeddings.py
Purpose: Produce embeddings for semantic indexing using an OpenAI-compatible embeddings endpoint.
Product/business importance: Enables Milestone 3 semantic retrieval (vector search).

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class EmbeddingsConfig:
    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float
    embeddings_path: str

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_EMBED_") -> "EmbeddingsConfig":
        base_url = os.environ.get(f"{prefix}BASE_URL", "").rstrip("/")
        model = os.environ.get(f"{prefix}MODEL", "")
        api_key = os.environ.get(f"{prefix}API_KEY")
        timeout_seconds = float(os.environ.get(f"{prefix}TIMEOUT_SECONDS", "60"))
        embeddings_path = os.environ.get(f"{prefix}EMBEDDINGS_PATH", "/api/v1/embeddings")
        if not base_url:
            raise ValueError(f"Missing {prefix}BASE_URL")
        if not model:
            raise ValueError(f"Missing {prefix}MODEL")
        return EmbeddingsConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            embeddings_path=embeddings_path,
        )


class OpenAiCompatibleEmbeddingsClient:
    def __init__(self, config: EmbeddingsConfig):
        self._config = config

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._config.base_url}{self._config.embeddings_path}"
        payload = {"model": self._config.model, "input": texts}

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        items = data.get("data")
        if not isinstance(items, list):
            raise RuntimeError("Embeddings response missing data list")

        vectors: list[list[float]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            emb = item.get("embedding")
            if not isinstance(emb, list):
                raise RuntimeError("Embeddings response item missing embedding")
            vectors.append([float(x) for x in emb])

        if len(vectors) != len(texts):
            raise RuntimeError("Embeddings response size mismatch")

        return vectors


class HashEmbeddingsClient:
    def __init__(self, *, dim: int = 384):
        self._dim = dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8", errors="ignore")).digest()
            base = [(b / 255.0) for b in h]
            out: list[float] = []
            while len(out) < self._dim:
                out.extend(base)
            vectors.append(out[: self._dim])
        return vectors


def embeddings_client_from_env() -> OpenAiCompatibleEmbeddingsClient | HashEmbeddingsClient:
    mode = os.environ.get("CODEKNOWL_EMBED_MODE", "http").strip().lower()
    if mode == "hash":
        dim = int(os.environ.get("CODEKNOWL_EMBED_HASH_DIM", "384"))
        return HashEmbeddingsClient(dim=dim)
    return OpenAiCompatibleEmbeddingsClient(EmbeddingsConfig.from_env())
