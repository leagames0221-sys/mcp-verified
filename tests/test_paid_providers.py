"""Tests for `mcp_verified.providers.{anthropic,openai,gemini}` — T-08."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from mcp_verified.providers import (
    ANTHROPIC_API_KEY_ENV,
    ANTHROPIC_DEFAULT_MODEL,
    GEMINI_API_KEY_ENV,
    GEMINI_DEFAULT_MODEL,
    OPENAI_API_KEY_ENV,
    OPENAI_DEFAULT_MODEL,
    PAID_OPT_IN_ENV_VAR,
    PAID_OPT_IN_VALUE,
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    PaidProviderMissingKeyError,
    PaidProviderRefusedError,
    ProviderError,
    assert_paid_opt_in,
)


# Reusable parameter set: (ProviderCls, vendor key env var, sample envelope, expected parsed dict).
def _sample_envelopes() -> list[tuple[type, str, dict[str, Any]]]:
    return [
        (
            AnthropicProvider,
            ANTHROPIC_API_KEY_ENV,
            {
                "content": [
                    {"type": "text", "text": json.dumps({"findings": [{"rule_id": "X"}]})}
                ]
            },
        ),
        (
            OpenAIProvider,
            OPENAI_API_KEY_ENV,
            {
                "choices": [
                    {"message": {"content": json.dumps({"findings": [{"rule_id": "X"}]})}}
                ]
            },
        ),
        (
            GeminiProvider,
            GEMINI_API_KEY_ENV,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps({"findings": [{"rule_id": "X"}]})}]
                        }
                    }
                ]
            },
        ),
    ]


# ---------- Opt-in gate ----------


class TestAssertPaidOptIn:
    def test_raises_when_env_var_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(PAID_OPT_IN_ENV_VAR, raising=False)
        with pytest.raises(PaidProviderRefusedError):
            assert_paid_opt_in("test")

    def test_raises_when_env_var_value_wrong(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, "yes")
        with pytest.raises(PaidProviderRefusedError):
            assert_paid_opt_in("test")

    def test_passes_when_env_var_set_to_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, PAID_OPT_IN_VALUE)
        assert_paid_opt_in("test")  # no raise


# ---------- Refused-by-default behaviour ----------


class TestRefusedByDefault:
    @pytest.mark.parametrize("provider_cls,key_env,_envelope", _sample_envelopes())
    def test_refused_without_opt_in_even_with_key_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
        provider_cls: type,
        key_env: str,
        _envelope: dict[str, Any],
    ) -> None:
        """AC-3.5: refusal must fire even when the vendor key is present."""
        monkeypatch.delenv(PAID_OPT_IN_ENV_VAR, raising=False)
        monkeypatch.setenv(key_env, "sk-test-key")
        provider = provider_cls()
        with pytest.raises(PaidProviderRefusedError):
            provider.query("prompt", {})

    @pytest.mark.parametrize("provider_cls,key_env,_envelope", _sample_envelopes())
    def test_refused_with_wrong_opt_in_value(
        self,
        monkeypatch: pytest.MonkeyPatch,
        provider_cls: type,
        key_env: str,
        _envelope: dict[str, Any],
    ) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, "true")
        monkeypatch.setenv(key_env, "sk-test-key")
        provider = provider_cls()
        with pytest.raises(PaidProviderRefusedError):
            provider.query("prompt", {})


# ---------- Missing-key behaviour ----------


class TestMissingKey:
    @pytest.mark.parametrize("provider_cls,key_env,_envelope", _sample_envelopes())
    def test_opt_in_but_no_key_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        provider_cls: type,
        key_env: str,
        _envelope: dict[str, Any],
    ) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, PAID_OPT_IN_VALUE)
        monkeypatch.delenv(key_env, raising=False)
        provider = provider_cls()
        with pytest.raises(PaidProviderMissingKeyError):
            provider.query("prompt", {})


# ---------- Happy path (HTTP layer mocked) ----------


def _make_fake_urlopen(envelope: dict[str, Any]):
    """Build a fake urllib.request.urlopen that returns `envelope` as JSON."""
    captured: dict[str, Any] = {}

    class _FakeResponse:
        def __init__(self, body_bytes: bytes) -> None:
            self._buffer = io.BytesIO(body_bytes)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._buffer.close()
            return False

        def read(self) -> bytes:
            return self._buffer.read()

    def fake_urlopen(req, timeout=None):  # noqa: ARG001
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data
        return _FakeResponse(json.dumps(envelope).encode("utf-8"))

    return fake_urlopen, captured


class TestHappyPath:
    @pytest.mark.parametrize("provider_cls,key_env,envelope", _sample_envelopes())
    def test_query_returns_parsed_content(
        self,
        monkeypatch: pytest.MonkeyPatch,
        provider_cls: type,
        key_env: str,
        envelope: dict[str, Any],
    ) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, PAID_OPT_IN_VALUE)
        monkeypatch.setenv(key_env, "sk-fixture-key")
        fake_urlopen, _captured = _make_fake_urlopen(envelope)
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        provider = provider_cls()
        result = provider.query("prompt", {})
        assert result == {"findings": [{"rule_id": "X"}]}

    def test_anthropic_request_carries_x_api_key_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, PAID_OPT_IN_VALUE)
        monkeypatch.setenv(ANTHROPIC_API_KEY_ENV, "sk-fixture-key")
        envelope = {"content": [{"type": "text", "text": "{}"}]}
        fake_urlopen, captured = _make_fake_urlopen(envelope)
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        AnthropicProvider().query("prompt", {})
        # urllib normalises header names to title-case.
        assert captured["headers"].get("X-api-key") == "sk-fixture-key"
        assert captured["headers"].get("Anthropic-version")
        body = json.loads(captured["body"])
        assert body["model"] == ANTHROPIC_DEFAULT_MODEL
        assert body["messages"][0]["content"] == "prompt"

    def test_openai_request_carries_bearer_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, PAID_OPT_IN_VALUE)
        monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-fixture-key")
        envelope = {"choices": [{"message": {"content": "{}"}}]}
        fake_urlopen, captured = _make_fake_urlopen(envelope)
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        OpenAIProvider().query("prompt", {})
        assert captured["headers"].get("Authorization") == "Bearer sk-fixture-key"
        body = json.loads(captured["body"])
        assert body["model"] == OPENAI_DEFAULT_MODEL
        assert body["response_format"] == {"type": "json_object"}
        assert body["temperature"] == 0.0

    def test_gemini_request_carries_key_in_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PAID_OPT_IN_ENV_VAR, PAID_OPT_IN_VALUE)
        monkeypatch.setenv(GEMINI_API_KEY_ENV, "abc-fixture-key")
        envelope = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        fake_urlopen, captured = _make_fake_urlopen(envelope)
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        GeminiProvider().query("prompt", {})
        # The key lives in the URL query string for Gemini, not in headers.
        assert "key=abc-fixture-key" in captured["url"]
        assert GEMINI_DEFAULT_MODEL in captured["url"]
        body = json.loads(captured["body"])
        assert body["generationConfig"]["responseMimeType"] == "application/json"


# ---------- Error hierarchy ----------


class TestErrorHierarchy:
    def test_refused_is_provider_error(self) -> None:
        assert issubclass(PaidProviderRefusedError, ProviderError)

    def test_missing_key_is_provider_error(self) -> None:
        assert issubclass(PaidProviderMissingKeyError, ProviderError)

    def test_provider_names_set(self) -> None:
        assert AnthropicProvider().name == "anthropic"
        assert OpenAIProvider().name == "openai"
        assert GeminiProvider().name == "gemini"
