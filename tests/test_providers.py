"""Tests for `mcp_verified.providers` — T-07 acceptance surface."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from mcp_verified.providers import (
    EMPTY_FINDINGS,
    OLLAMA_DEFAULT_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
    MockProvider,
    OllamaProvider,
    Provider,
    ProviderError,
    ProviderResponseError,
    ProviderUnreachableError,
    query_with_fallback,
)

# ---------- Mock provider ----------


class TestMockProvider:
    def test_returns_empty_findings(self) -> None:
        result = MockProvider().query("anything", {})
        assert result == EMPTY_FINDINGS

    def test_returns_isolated_copy(self) -> None:
        """Mutating the response must not corrupt the shared default."""
        result = MockProvider().query("anything", {})
        result["findings"].append({"rule_id": "TEST"})
        # Re-query and verify the default is untouched.
        assert MockProvider().query("anything", {}) == {"findings": []}

    def test_provider_name(self) -> None:
        assert MockProvider().name == "mock"

    def test_is_a_provider(self) -> None:
        assert isinstance(MockProvider(), Provider)

    def test_no_network_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        called: list[str] = []

        def spy(*args, **kwargs):  # noqa: ARG001
            called.append("urlopen")
            raise AssertionError("MockProvider must not invoke urllib.urlopen")

        monkeypatch.setattr(urllib.request, "urlopen", spy)
        MockProvider().query("p", {})
        assert called == []


# ---------- Ollama provider — fixture HTTP server ----------


class _OllamaHandler(BaseHTTPRequestHandler):
    """Programmable fixture server. `response_body` is set per test."""

    response_body: bytes = b"{}"
    response_status: int = 200
    captured_request_body: bytes | None = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Suppress noisy stderr during tests.
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).captured_request_body = body
        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.response_body)))
        self.end_headers()
        self.wfile.write(self.response_body)


@pytest.fixture
def fixture_server():
    """Spin up a one-port HTTPServer on a free port, return (server, port)."""
    server = HTTPServer(("127.0.0.1", 0), _OllamaHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
        # Reset class-level state between tests.
        _OllamaHandler.response_body = b"{}"
        _OllamaHandler.response_status = 200
        _OllamaHandler.captured_request_body = None


def _set_ollama_response(content_json: dict[str, Any]) -> None:
    """Set the next /api/chat response to wrap `content_json` as
    Ollama would.
    """
    envelope = {
        "model": "gemma3:4b",
        "message": {"role": "assistant", "content": json.dumps(content_json)},
        "done": True,
    }
    _OllamaHandler.response_body = json.dumps(envelope).encode("utf-8")


class TestOllamaProviderHappyPath:
    def test_returns_parsed_content(self, fixture_server) -> None:
        _, port = fixture_server
        _set_ollama_response({"findings": [{"rule_id": "X"}]})
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{port}")
        result = provider.query("scan this", {})
        assert result == {"findings": [{"rule_id": "X"}]}

    def test_payload_pins_format_json(self, fixture_server) -> None:
        _, port = fixture_server
        _set_ollama_response({"findings": []})
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{port}")
        provider.query("ping", {})
        body = _OllamaHandler.captured_request_body
        assert body is not None
        sent = json.loads(body)
        assert sent["format"] == "json"
        assert sent["stream"] is False
        assert sent["options"]["temperature"] == 0.0
        assert sent["model"] == OLLAMA_DEFAULT_MODEL
        assert sent["messages"][0]["content"] == "ping"

    def test_custom_temperature_and_model_propagate(self, fixture_server) -> None:
        _, port = fixture_server
        _set_ollama_response({"findings": []})
        provider = OllamaProvider(
            base_url=f"http://127.0.0.1:{port}",
            model="qwen2.5:7b",
            temperature=0.3,
        )
        provider.query("ping", {})
        body = _OllamaHandler.captured_request_body
        assert body is not None
        sent = json.loads(body)
        assert sent["model"] == "qwen2.5:7b"
        assert sent["options"]["temperature"] == 0.3


class TestOllamaProviderErrorPaths:
    def test_unreachable_raises_provider_unreachable(self) -> None:
        # Port 1 is not bound; expect URLError -> ProviderUnreachableError.
        provider = OllamaProvider(base_url="http://127.0.0.1:1", timeout_seconds=2.0)
        with pytest.raises(ProviderUnreachableError):
            provider.query("ping", {})

    def test_non_json_envelope_raises_response_error(self, fixture_server) -> None:
        _, port = fixture_server
        _OllamaHandler.response_body = b"not json at all"
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{port}")
        with pytest.raises(ProviderResponseError):
            provider.query("ping", {})

    def test_missing_message_raises_response_error(self, fixture_server) -> None:
        _, port = fixture_server
        _OllamaHandler.response_body = json.dumps({"done": True}).encode("utf-8")
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{port}")
        with pytest.raises(ProviderResponseError):
            provider.query("ping", {})

    def test_content_not_json_raises_response_error(self, fixture_server) -> None:
        _, port = fixture_server
        envelope = {"message": {"content": "this is not JSON"}}
        _OllamaHandler.response_body = json.dumps(envelope).encode("utf-8")
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{port}")
        with pytest.raises(ProviderResponseError):
            provider.query("ping", {})

    def test_content_array_raises_response_error(self, fixture_server) -> None:
        _, port = fixture_server
        envelope = {"message": {"content": "[1, 2, 3]"}}
        _OllamaHandler.response_body = json.dumps(envelope).encode("utf-8")
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{port}")
        with pytest.raises(ProviderResponseError):
            provider.query("ping", {})


class TestOllamaProviderDefaults:
    def test_default_base_and_model(self) -> None:
        provider = OllamaProvider()
        assert provider.base_url == OLLAMA_DEFAULT_BASE_URL
        assert provider.model == OLLAMA_DEFAULT_MODEL
        assert provider.temperature == 0.0
        assert provider.name == "ollama"


# ---------- Fallback helper ----------


class TestQueryWithFallback:
    def test_returns_primary_when_primary_succeeds(self) -> None:
        primary = MockProvider()
        fallback = MockProvider()
        # Subclass to give them distinguishable names.
        primary.name = "primary"
        fallback.name = "fallback"
        result, name = query_with_fallback(primary, fallback, "p", {})
        assert name == "primary"
        assert result == EMPTY_FINDINGS

    def test_falls_back_on_unreachable(self) -> None:
        class _BrokenProvider(Provider):
            name = "ollama"

            def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
                raise ProviderUnreachableError("simulated")

        result, name = query_with_fallback(_BrokenProvider(), MockProvider(), "p", {})
        assert name == "mock"
        assert result == EMPTY_FINDINGS

    def test_does_not_swallow_response_error(self) -> None:
        class _BrokenProvider(Provider):
            name = "ollama"

            def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
                raise ProviderResponseError("garbage")

        with pytest.raises(ProviderResponseError):
            query_with_fallback(_BrokenProvider(), MockProvider(), "p", {})


# ---------- Provider ABC ----------


class TestProviderABC:
    def test_cannot_instantiate_abstract_base(self) -> None:
        with pytest.raises(TypeError):
            Provider()  # type: ignore[abstract]

    def test_error_hierarchy(self) -> None:
        assert issubclass(ProviderUnreachableError, ProviderError)
        assert issubclass(ProviderResponseError, ProviderError)
        assert issubclass(ProviderError, Exception)
