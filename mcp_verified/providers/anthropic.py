"""Anthropic Claude provider (paid, refused-by-default).

Implements T-08 (Anthropic path) / AC-3.5.

POST to `https://api.anthropic.com/v1/messages` with the standard
`x-api-key` header and `anthropic-version: 2023-06-01`. Default model
is `claude-haiku-4-5-20251001` (the cost-conscious choice per the
Phase 1 four-constraint envelope).
"""

from __future__ import annotations

from typing import Any

from mcp_verified.providers._paid import _PaidProviderBase

ANTHROPIC_API_BASE = "https://api.anthropic.com"
ANTHROPIC_MESSAGES_PATH = "/v1/messages"
ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(_PaidProviderBase):
    name = "anthropic"
    api_key_env_var = ANTHROPIC_API_KEY_ENV
    default_api_base = ANTHROPIC_API_BASE
    default_model = ANTHROPIC_DEFAULT_MODEL

    def __init__(
        self,
        *,
        api_base: str | None = None,
        model: str | None = None,
        max_tokens: int = ANTHROPIC_DEFAULT_MAX_TOKENS,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(api_base=api_base, model=model, timeout_seconds=timeout_seconds)
        self.max_tokens = max_tokens

    def _endpoint_url(self, api_base: str, api_key: str) -> str:
        del api_key  # Anthropic puts the key in the header, not the URL.
        return f"{api_base}{ANTHROPIC_MESSAGES_PATH}"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _extract_content(self, envelope: dict[str, Any]) -> dict[str, Any]:
        import json

        content = envelope["content"]
        # Anthropic returns `content` as a list of typed blocks; the
        # text payload is the first text-typed block.
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block["text"]
                parsed = json.loads(text)
                if not isinstance(parsed, dict):
                    raise TypeError(
                        f"Anthropic parsed content is not an object: {type(parsed).__name__}"
                    )
                return parsed
        raise ValueError("Anthropic response did not contain a text block")
