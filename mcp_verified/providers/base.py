"""Provider abstract base class + the exception hierarchy used by every
implementation.

Implements T-07 / AC-3.1 / AC-3.2 / AC-3.3.

A Provider takes a prompt string and a structured-output schema and returns
a parsed JSON dict. Failure modes are surfaced as `ProviderError` subclasses
so the call site can distinguish "the LLM is unreachable" (fallback to mock)
from "the LLM returned garbage" (record an error finding).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderError(Exception):
    """Base class for any provider failure."""


class ProviderUnreachableError(ProviderError):
    """Raised when the provider cannot be contacted (connection refused,
    timeout, DNS failure). Callers typically fall back to `MockProvider`.
    """


class ProviderResponseError(ProviderError):
    """Raised when the provider returned a response that could not be parsed
    or did not match the requested schema. Callers typically record an
    `error` finding for the check and continue with the next candidate.
    """


class Provider(ABC):
    """Single-method interface: `query(prompt, schema) -> parsed JSON dict`.

    Concrete providers set the class attribute `name` so audit manifests can
    record which provider produced a given verdict.
    """

    name: str = "abstract"

    @abstractmethod
    def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Run one prompt-response round.

        Parameters
        ----------
        prompt
            The full prompt text.
        schema
            A dict describing the expected response shape. Phase 1 does not
            run full JSON-Schema validation; concrete providers may use the
            schema as a hint when negotiating structured-output mode with
            the underlying LLM.

        Returns
        -------
        dict[str, Any]
            Parsed JSON object returned by the LLM.

        Raises
        ------
        ProviderUnreachableError
            Connection failure. Callers may retry against `MockProvider`.
        ProviderResponseError
            Non-JSON response or response that fails the agreed schema.
        """
        raise NotImplementedError


def query_with_fallback(
    primary: Provider,
    fallback: Provider,
    prompt: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Convenience: call `primary.query`, swap to `fallback` on unreachable.

    Returns a `(response, provider_name)` pair so the caller can record
    `tools_used` in the audit manifest with the provider that actually
    produced the verdict. Response errors are *not* caught here — they
    propagate to the caller as an error finding signal.
    """
    try:
        return primary.query(prompt, schema), primary.name
    except ProviderUnreachableError:
        return fallback.query(prompt, schema), fallback.name
