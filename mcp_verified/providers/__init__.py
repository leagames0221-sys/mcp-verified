"""LLM provider subpackage.

Phase 1 ships the Provider ABC plus the Ollama (default) and mock (fallback)
implementations. Paid providers (Anthropic, OpenAI, Gemini) land in T-08 and
are refused at runtime unless explicitly opted in.
"""

from mcp_verified.providers.base import (
    Provider,
    ProviderError,
    ProviderResponseError,
    ProviderUnreachableError,
    query_with_fallback,
)
from mcp_verified.providers.mock import EMPTY_FINDINGS, MockProvider
from mcp_verified.providers.ollama import (
    OLLAMA_DEFAULT_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
    OllamaProvider,
)

__all__ = [
    "EMPTY_FINDINGS",
    "MockProvider",
    "OLLAMA_DEFAULT_BASE_URL",
    "OLLAMA_DEFAULT_MODEL",
    "OllamaProvider",
    "Provider",
    "ProviderError",
    "ProviderResponseError",
    "ProviderUnreachableError",
    "query_with_fallback",
]
