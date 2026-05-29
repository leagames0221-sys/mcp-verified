"""OpenAI provider (paid, refused-by-default).

Implements T-08 (OpenAI path) / AC-3.5.

POST to `https://api.openai.com/v1/chat/completions` with bearer auth.
Phase 1 default model is `gpt-5-mini` for cost; the user can override.
Structured output is requested via `response_format: {"type": "json_object"}`.
"""

from __future__ import annotations

from typing import Any

from mcp_verified.providers._paid import _PaidProviderBase

OPENAI_API_BASE = "https://api.openai.com"
OPENAI_CHAT_PATH = "/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-5-mini"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


class OpenAIProvider(_PaidProviderBase):
    name = "openai"
    api_key_env_var = OPENAI_API_KEY_ENV
    default_api_base = OPENAI_API_BASE
    default_model = OPENAI_DEFAULT_MODEL

    def __init__(
        self,
        *,
        api_base: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(api_base=api_base, model=model, timeout_seconds=timeout_seconds)
        self.temperature = temperature

    def _endpoint_url(self, api_base: str, api_key: str) -> str:
        del api_key
        return f"{api_base}{OPENAI_CHAT_PATH}"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }

    def _extract_content(self, envelope: dict[str, Any]) -> dict[str, Any]:
        import json

        choices = envelope["choices"]
        message = choices[0]["message"]
        content = message["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise TypeError(f"OpenAI parsed content is not an object: {type(parsed).__name__}")
        return parsed
