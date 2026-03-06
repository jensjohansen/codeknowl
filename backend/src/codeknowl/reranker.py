"""File: backend/src/codeknowl/reranker.py
Purpose: Provide a configurable reranking step for semantic retrieval results.
Product/business importance: Improves answer quality by reordering retrieved chunks using a local-first reranker model
or a deterministic fallback, reducing hallucinations and improving citation relevance.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class Reranker(Protocol):
    def rerank(self, *, query: str, documents: list[str], top_n: int | None = None) -> list[float]:
        raise NotImplementedError


@dataclass(frozen=True)
class RerankerConfig:
    mode: str

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_RERANK_") -> "RerankerConfig":
        mode = os.environ.get(f"{prefix}MODE", "none").strip().lower()
        return RerankerConfig(mode=mode)


@dataclass(frozen=True)
class HttpRerankerConfig:
    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float
    rerank_path: str

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_RERANK_") -> "HttpRerankerConfig":
        base_url = os.environ.get(f"{prefix}BASE_URL", "").rstrip("/")
        model = os.environ.get(f"{prefix}MODEL", "")
        api_key = os.environ.get(f"{prefix}API_KEY")
        timeout_seconds = float(os.environ.get(f"{prefix}TIMEOUT_SECONDS", "30"))
        rerank_path = os.environ.get(f"{prefix}RERANK_PATH", "/api/v1/rerank")
        if not base_url:
            raise ValueError(f"Missing {prefix}BASE_URL")
        if not model:
            raise ValueError(f"Missing {prefix}MODEL")
        return HttpRerankerConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            rerank_path=rerank_path,
        )


class OpenAiCompatibleReranker:
    def __init__(self, config: HttpRerankerConfig):
        self._config = config

    def rerank(self, *, query: str, documents: list[str], top_n: int | None = None) -> list[float]:
        if not documents:
            return []

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._config.base_url}{self._config.rerank_path}"
        payload: dict[str, Any] = {
            "model": self._config.model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        scores = data.get("scores")
        if not isinstance(scores, list):
            raise RuntimeError("Rerank response missing scores list")

        out: list[float] = []
        for s in scores:
            out.append(float(s))

        if len(out) != len(documents):
            raise RuntimeError("Rerank response size mismatch")

        return out


class OverlapReranker:
    def _tokenize(self, text: str) -> set[str]:
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text.lower())
        return {t for t in tokens if t}

    def rerank(self, *, query: str, documents: list[str], top_n: int | None = None) -> list[float]:
        if not documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return [0.0 for _ in documents]

        scores: list[float] = []
        for doc in documents:
            document_tokens = self._tokenize(doc)
            if not document_tokens:
                scores.append(0.0)
                continue
            scores.append(float(len(query_tokens & document_tokens)) / float(len(query_tokens)))

        return scores


def reranker_from_env() -> Reranker | None:
    configuration = RerankerConfig.from_env()
    if configuration.mode in {"", "none", "off", "disabled"}:
        return None
    if configuration.mode in {"overlap", "deterministic"}:
        return OverlapReranker()
    if configuration.mode == "http":
        return OpenAiCompatibleReranker(HttpRerankerConfig.from_env())
    raise ValueError(f"Unsupported reranker mode: {configuration.mode}")
