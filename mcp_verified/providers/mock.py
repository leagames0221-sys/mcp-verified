"""Mock provider: deterministic, network-free, returns an empty-findings object.

Used both as the CI default (no Ollama running) and as the runtime fallback
when the configured provider raises `ProviderUnreachableError`.

The returned shape is conservative and matches the Phase 1 default check
schema `{"findings": [...]}`. Downstream code can rely on the presence of
the `findings` key and an iterable value.
"""

from __future__ import annotations

from typing import Any

from mcp_verified.providers.base import Provider

EMPTY_FINDINGS: dict[str, Any] = {"findings": []}


class MockProvider(Provider):
    """Always-succeeds, always-empty provider.

    Calls do not touch the network. The same `EMPTY_FINDINGS` dict is
    returned every time so deterministic CI runs are byte-identical.
    """

    name = "mock"

    def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        # Build a fresh structure each call so downstream mutations cannot
        # bleed into the shared `EMPTY_FINDINGS` default or into the next
        # caller's result.
        return {"findings": []}
