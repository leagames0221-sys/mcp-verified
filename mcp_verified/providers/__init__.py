"""LLM provider subpackage.

Phase 1 ships the Provider ABC, the Ollama (default) and mock (fallback)
implementations, plus three paid providers (Anthropic, OpenAI, Gemini)
which are refused at runtime unless `MCP_VERIFIED_PAID_PROVIDER_OPT_IN=1`
is set explicitly, even when the vendor's API-key env var is present.
"""

from mcp_verified.providers._paid import (
    PAID_OPT_IN_ENV_VAR,
    PAID_OPT_IN_VALUE,
    PaidProviderMissingKeyError,
    PaidProviderRefusedError,
    assert_paid_opt_in,
)
from mcp_verified.providers.anthropic import (
    ANTHROPIC_API_KEY_ENV,
    ANTHROPIC_DEFAULT_MODEL,
    AnthropicProvider,
)
from mcp_verified.providers.base import (
    Provider,
    ProviderError,
    ProviderResponseError,
    ProviderUnreachableError,
    query_with_fallback,
)
from mcp_verified.providers.gemini import (
    GEMINI_API_KEY_ENV,
    GEMINI_DEFAULT_MODEL,
    GeminiProvider,
)
from mcp_verified.providers.mock import EMPTY_FINDINGS, MockProvider
from mcp_verified.providers.ollama import (
    OLLAMA_DEFAULT_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
    OllamaProvider,
)
from mcp_verified.providers.openai import (
    OPENAI_API_KEY_ENV,
    OPENAI_DEFAULT_MODEL,
    OpenAIProvider,
)

__all__ = [
    "ANTHROPIC_API_KEY_ENV",
    "ANTHROPIC_DEFAULT_MODEL",
    "AnthropicProvider",
    "EMPTY_FINDINGS",
    "GEMINI_API_KEY_ENV",
    "GEMINI_DEFAULT_MODEL",
    "GeminiProvider",
    "MockProvider",
    "OLLAMA_DEFAULT_BASE_URL",
    "OLLAMA_DEFAULT_MODEL",
    "OPENAI_API_KEY_ENV",
    "OPENAI_DEFAULT_MODEL",
    "OllamaProvider",
    "OpenAIProvider",
    "PAID_OPT_IN_ENV_VAR",
    "PAID_OPT_IN_VALUE",
    "PaidProviderMissingKeyError",
    "PaidProviderRefusedError",
    "Provider",
    "ProviderError",
    "ProviderResponseError",
    "ProviderUnreachableError",
    "assert_paid_opt_in",
    "query_with_fallback",
]
