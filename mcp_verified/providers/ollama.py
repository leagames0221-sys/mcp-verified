"""Ollama provider: HTTP client for the local Ollama daemon.

Implements T-07 (Ollama path) / AC-3.1 / AC-3.2.

The default Phase 1 configuration is `gemma3:4b` at `temperature=0` against
`http://localhost:11434/api/chat` (ADR-004). Structured output is requested
via Ollama's `format: "json"` option; the response content is then parsed
as JSON.

This module uses stdlib `urllib` only — no runtime dependency added. The
network surface is `http://localhost:11434/*` only (AC-4.4).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from mcp_verified.providers.base import (
    Provider,
    ProviderResponseError,
    ProviderUnreachableError,
)

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "gemma3:4b"
OLLAMA_CHAT_PATH = "/api/chat"
DEFAULT_TIMEOUT_SECONDS = 30.0


class OllamaProvider(Provider):
    """HTTP client for Ollama's `/api/chat` endpoint.

    Parameters
    ----------
    base_url
        Origin of the Ollama daemon. Defaults to `http://localhost:11434`.
        Anything outside the AC-4.4 allowlist (`localhost:*`) is the
        caller's responsibility.
    model
        Model tag to request. Defaults to `gemma3:4b` (pinned per ADR-004).
    temperature
        Sampling temperature. Defaults to 0.0 for reproducibility.
    timeout_seconds
        Hard timeout on the HTTP request.
    """

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = OLLAMA_DEFAULT_BASE_URL,
        model: str = OLLAMA_DEFAULT_MODEL,
        temperature: float = 0.0,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def _build_payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "options": {"temperature": self.temperature},
            "stream": False,
        }

    def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del schema  # The schema is a hint; Ollama's `format: json` does the enforcement.
        payload = self._build_payload(prompt)
        url = f"{self.base_url}{OLLAMA_CHAT_PATH}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body_bytes = resp.read()
        except urllib.error.URLError as exc:
            raise ProviderUnreachableError(
                f"Ollama at {self.base_url} unreachable: {exc.reason}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise ProviderUnreachableError(
                f"Ollama at {self.base_url} request failed: {exc}"
            ) from exc

        try:
            envelope = json.loads(body_bytes)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(f"Ollama response envelope is not JSON: {exc}") from exc

        if not isinstance(envelope, dict):
            raise ProviderResponseError(
                f"Ollama response envelope is not an object: {type(envelope).__name__}"
            )

        message = envelope.get("message")
        if not isinstance(message, dict):
            raise ProviderResponseError("Ollama response missing 'message' object")

        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderResponseError("Ollama response message.content is not a string")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(f"Ollama message.content is not JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ProviderResponseError(
                f"Ollama parsed content is not an object: {type(parsed).__name__}"
            )

        return parsed
