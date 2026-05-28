"""Shared scaffolding for paid LLM providers.

Implements T-08 / AC-3.5 / AC-4.4.

A paid provider is one whose default code path issues an HTTPS request to a
vendor's billed API. Phase 1 refuses to do that unless the user has
explicitly opted in via an environment variable, even when the vendor's
API-key environment variable is present.

The opt-in gate is enforced at the start of every `query` call. Subclasses
implement four vendor-specific hooks (`_endpoint_url`, `_headers`,
`_payload`, `_extract_content`) and inherit the gate, the HTTP plumbing,
and the error-mapping logic from `_PaidProviderBase`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import abstractmethod
from typing import Any

from mcp_verified.providers.base import (
    Provider,
    ProviderError,
    ProviderResponseError,
    ProviderUnreachableError,
)

PAID_OPT_IN_ENV_VAR = "MCP_VERIFIED_PAID_PROVIDER_OPT_IN"
PAID_OPT_IN_VALUE = "1"
DEFAULT_PAID_TIMEOUT_SECONDS = 60.0


class PaidProviderRefusedError(ProviderError):
    """Raised when a paid provider is invoked without the opt-in env var.

    The presence of the vendor's API key in the environment is **not**
    sufficient. The user must additionally set the opt-in variable so the
    refusal cannot happen by accident from a leftover key in the shell
    environment.
    """


class PaidProviderMissingKeyError(ProviderError):
    """Raised when the opt-in is granted but the vendor key is missing."""


def assert_paid_opt_in(provider_name: str) -> None:
    """Raise PaidProviderRefusedError unless the opt-in env var equals "1"."""
    actual = os.environ.get(PAID_OPT_IN_ENV_VAR, "")
    if actual != PAID_OPT_IN_VALUE:
        raise PaidProviderRefusedError(
            f"{provider_name} provider refused: set "
            f"{PAID_OPT_IN_ENV_VAR}={PAID_OPT_IN_VALUE} explicitly to enable."
        )


class _PaidProviderBase(Provider):
    """Common HTTP plumbing for paid providers.

    Subclasses set the class attributes `name`, `api_key_env_var`,
    `default_api_base`, and `default_model`. They implement four hooks:

    - `_endpoint_url(api_base, api_key)` returns the request URL.
    - `_headers(api_key)` returns the HTTP request headers.
    - `_payload(prompt)` returns the JSON-serializable request body.
    - `_extract_content(envelope)` returns the parsed dict to surface to
      the caller from the vendor's response envelope.
    """

    api_key_env_var: str = "UNSET"
    default_api_base: str = "https://example.invalid"
    default_model: str = "unset"

    def __init__(
        self,
        *,
        api_base: str | None = None,
        model: str | None = None,
        timeout_seconds: float = DEFAULT_PAID_TIMEOUT_SECONDS,
    ) -> None:
        self.api_base = (api_base or self.default_api_base).rstrip("/")
        self.model = model or self.default_model
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def _endpoint_url(self, api_base: str, api_key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def _headers(self, api_key: str) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def _payload(self, prompt: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def _extract_content(self, envelope: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del schema  # vendors handle structured-output via per-vendor knobs in _payload.
        assert_paid_opt_in(self.name)

        api_key = os.environ.get(self.api_key_env_var, "")
        if not api_key:
            raise PaidProviderMissingKeyError(
                f"{self.name} provider opted-in but {self.api_key_env_var} is not set."
            )

        url = self._endpoint_url(self.api_base, api_key)
        headers = self._headers(api_key)
        payload = self._payload(prompt)

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body_bytes = resp.read()
        except urllib.error.URLError as exc:
            raise ProviderUnreachableError(
                f"{self.name} at {self.api_base} unreachable: {exc.reason}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise ProviderUnreachableError(
                f"{self.name} at {self.api_base} request failed: {exc}"
            ) from exc

        try:
            envelope = json.loads(body_bytes)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(
                f"{self.name} response envelope is not JSON: {exc}"
            ) from exc

        if not isinstance(envelope, dict):
            raise ProviderResponseError(
                f"{self.name} response envelope is not an object: {type(envelope).__name__}"
            )

        try:
            return self._extract_content(envelope)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderResponseError(
                f"{self.name} content extraction failed: {exc}"
            ) from exc
