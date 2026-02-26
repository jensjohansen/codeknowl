"""File: backend/src/codeknowl/llm.py
Purpose: Provide a minimal OpenAI-compatible HTTP client for lemonade-server model endpoints.
Product/business importance: Enables Milestone 1 semi-intelligent answers grounded in evidence without cloud
dependencies.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float
    chat_completions_path: str
    models_path: str

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_LLM_") -> "LlmConfig":
        base_url = os.environ.get(f"{prefix}BASE_URL", "").rstrip("/")
        model = os.environ.get(f"{prefix}MODEL", "")
        api_key = os.environ.get(f"{prefix}API_KEY")
        timeout_seconds = float(os.environ.get(f"{prefix}TIMEOUT_SECONDS", "60"))
        chat_completions_path = os.environ.get(f"{prefix}CHAT_COMPLETIONS_PATH", "/api/v1/chat/completions")
        models_path = os.environ.get(f"{prefix}MODELS_PATH", "/api/v1/models")
        if not base_url:
            raise ValueError(f"Missing {prefix}BASE_URL")
        if not model:
            raise ValueError(f"Missing {prefix}MODEL")
        return LlmConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            chat_completions_path=chat_completions_path,
            models_path=models_path,
        )


class OpenAiCompatibleClient:
    def __init__(self, config: LlmConfig):
        self._config = config

    def chat(self, *, system: str, user: str) -> str:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._config.base_url}{self._config.chat_completions_path}"
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices")
        message = (choices[0].get("message") or {}).get("content")
        if not isinstance(message, str) or not message.strip():
            raise RuntimeError("LLM response missing message content")
        return message

    def list_models(self) -> list[dict[str, object]]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._config.base_url}{self._config.models_path}"
        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models = data.get("data")
        if not isinstance(models, list):
            return []
        return [m for m in models if isinstance(m, dict)]
