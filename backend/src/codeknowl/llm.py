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
    """Connection and model settings for an OpenAI-compatible LLM endpoint.

    Why this exists:
    - Operators need to configure endpoint, model, auth, and paths via environment.
    """

    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float
    chat_completions_path: str
    models_path: str

    @staticmethod
    def from_env(prefix: str = "CODEKNOWL_LLM_") -> "LlmConfig":
        """Load LLM configuration from environment variables.

        Why this exists:
        - The backend should be configurable via environment without code changes.
        """
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

    @staticmethod
    def try_from_env(prefix: str = "CODEKNOWL_LLM_") -> "LlmConfig | None":
        """Load LLM configuration from environment variables, returning None if incomplete.

        Why this exists:
        - The backend should be able to run without an LLM for deterministic-only QA.
        """
        base_url = os.environ.get(f"{prefix}BASE_URL", "").strip()
        model = os.environ.get(f"{prefix}MODEL", "").strip()
        if not base_url or not model:
            return None
        return LlmConfig.from_env(prefix=prefix)


@dataclass(frozen=True)
class LlmProfiles:
    """Three LLM configurations for multi-profile QA synthesis.

    Why this exists:
    - Multi-model QA uses distinct profiles: coding, general, and synthesizer.
    """

    coding: LlmConfig
    general: LlmConfig
    synth: LlmConfig

    @staticmethod
    def from_env() -> "LlmProfiles | None":
        """Load the three LLM roles used for QA synthesis.

        Backward compatible behavior:
        - If role-specific env vars are not present, fall back to CODEKNOWL_LLM_*.
        - If SYNTH is not configured, defaults to GENERAL.

        Why this exists:
        - Operators can configure three distinct models while maintaining backward compatibility.
        """
        default = LlmConfig.try_from_env(prefix="CODEKNOWL_LLM_")
        if default is None:
            return None

        coding = LlmConfig.try_from_env(prefix="CODEKNOWL_LLM_CODING_") or default
        general = LlmConfig.try_from_env(prefix="CODEKNOWL_LLM_GENERAL_") or default
        synth = LlmConfig.try_from_env(prefix="CODEKNOWL_LLM_SYNTH_") or general
        return LlmProfiles(coding=coding, general=general, synth=synth)


class OpenAiCompatibleClient:
    """HTTP client for OpenAI-compatible chat completions and model listing.

    Why this exists:
    - The backend needs to communicate with lemonade-server or similar endpoints using the OpenAI API format.
    """

    def __init__(self, config: LlmConfig):
        self._config = config

    def chat(self, *, system: str, user: str) -> str:
        """Send a chat completion request and return the assistant’s message.

        Why this exists:
        - QA synthesis needs to send system/user prompts and extract the assistant’s response.
        """
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
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices")
        message = (choices[0].get("message") or {}).get("content")
        if not isinstance(message, str) or not message.strip():
            raise RuntimeError("LLM response missing message content")
        return message

    def list_models(self) -> list[dict[str, object]]:
        """List available models from the endpoint.

        Why this exists:
        - Operators and health checks need to verify that the LLM endpoint is reachable and serving models.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._config.base_url}{self._config.models_path}"
        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        models = data.get("data")
        if not isinstance(models, list):
            return []
        return [m for m in models if isinstance(m, dict)]
