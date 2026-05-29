"""Gemini provider (paid, refused-by-default).

Implements T-08 (Gemini path) / AC-3.5.

POST to `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<key>`.
Structured output is requested via `generationConfig.responseMimeType: application/json`.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mcp_verified.providers._paid import _PaidProviderBase

GEMINI_API_BASE = "https://generativelanguage.googleapis.com"
GEMINI_GENERATE_PATH_TEMPLATE = "/v1beta/models/{model}:generateContent"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"


class GeminiProvider(_PaidProviderBase):
    name = "gemini"
    api_key_env_var = GEMINI_API_KEY_ENV
    default_api_base = GEMINI_API_BASE
    default_model = GEMINI_DEFAULT_MODEL

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
        path = GEMINI_GENERATE_PATH_TEMPLATE.format(model=quote(self.model, safe=""))
        return f"{api_base}{path}?key={quote(api_key, safe='')}"

    def _headers(self, api_key: str) -> dict[str, str]:
        del api_key  # Gemini puts the key in the URL, not the header.
        return {"Content-Type": "application/json"}

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
            },
        }

    def _extract_content(self, envelope: dict[str, Any]) -> dict[str, Any]:
        import json

        candidates = envelope["candidates"]
        parts = candidates[0]["content"]["parts"]
        text = parts[0]["text"]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise TypeError(f"Gemini parsed content is not an object: {type(parsed).__name__}")
        return parsed
