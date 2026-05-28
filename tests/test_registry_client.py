"""Tests for `mcp_verified.registry.client` — T-02 acceptance surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_verified.registry.client import (
    DEFAULT_PAGE_SIZE,
    RegistryClient,
    RegistryEntry,
    integration_tests_enabled,
    parse_response,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "registry-snapshot-2026-05-28.json"


@pytest.fixture
def fixture_payload() -> dict:
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Unit tests against the recorded fixture ----------


class TestParseResponse:
    def test_parses_fixture_envelope(self, fixture_payload: dict) -> None:
        entries, next_cursor = parse_response(fixture_payload)
        assert len(entries) == 3
        assert next_cursor is not None and ":" in next_cursor

    def test_entry_field_types(self, fixture_payload: dict) -> None:
        entries, _ = parse_response(fixture_payload)
        for entry in entries:
            assert isinstance(entry, RegistryEntry)
            assert isinstance(entry.name, str) and entry.name
            assert isinstance(entry.version, str) and entry.version
            assert isinstance(entry.description, str)
            assert isinstance(entry.remotes, tuple)
            assert isinstance(entry.is_latest, bool)

    def test_github_filter_isolates_repo_backed_servers(self, fixture_payload: dict) -> None:
        entries, _ = parse_response(fixture_payload)
        github_backed = [e for e in entries if e.is_github_source]
        # The fixture's third record (ac.tandem/docs-mcp) carries a GitHub repo;
        # the first two (ac.inference.sh/mcp v1.0.0, v1.0.1) are remote-only.
        assert len(github_backed) == 1
        assert github_backed[0].name == "ac.tandem/docs-mcp"
        assert github_backed[0].repository_url is not None
        assert github_backed[0].repository_url.startswith("https://github.com/")

    def test_is_latest_dedup_axis(self, fixture_payload: dict) -> None:
        entries, _ = parse_response(fixture_payload)
        latest = [e for e in entries if e.is_latest]
        non_latest = [e for e in entries if not e.is_latest]
        # The fixture intentionally captures two versions of the same logical
        # server; exactly one is marked isLatest=true.
        assert len(latest) >= 1
        assert len(non_latest) >= 1

    def test_rejects_non_object_payload(self) -> None:
        with pytest.raises(ValueError):
            parse_response([])  # type: ignore[arg-type]

    def test_rejects_non_list_servers_field(self) -> None:
        with pytest.raises(ValueError):
            parse_response({"servers": "not a list"})  # type: ignore[arg-type]

    def test_skips_malformed_envelope_without_crashing(self) -> None:
        payload = {
            "servers": [
                {"server": {"name": "ok/server", "version": "1.0.0"}, "_meta": {}},
                {"server": "not a dict"},  # malformed; should be skipped
                {"not_a_server_key": True},  # malformed; should be skipped
            ],
            "metadata": {"nextCursor": None, "count": 1},
        }
        entries, next_cursor = parse_response(payload)
        assert len(entries) == 1
        assert entries[0].name == "ok/server"
        assert next_cursor is None


# ---------- Unit tests on the RegistryClient cache layer ----------


class TestRegistryClientCache:
    def test_cache_round_trip(self, tmp_path: Path, fixture_payload: dict) -> None:
        client = RegistryClient(cache_dir=tmp_path, cache_ttl_seconds=3600)
        # Manually prime the cache with the fixture as if a real fetch ran.
        client._save_cache(cursor=None, payload=fixture_payload)
        loaded = client._load_cache(cursor=None)
        assert loaded == fixture_payload

    def test_cache_miss_when_expired(
        self, tmp_path: Path, fixture_payload: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = RegistryClient(cache_dir=tmp_path, cache_ttl_seconds=1)
        client._save_cache(cursor=None, payload=fixture_payload)
        # Simulate the cache entry being older than the TTL by patching time.
        import mcp_verified.registry.client as mod

        cache_path = client._cache_path(None)
        original_mtime = cache_path.stat().st_mtime
        monkeypatch.setattr(mod.time, "time", lambda: original_mtime + 100.0)
        assert client._load_cache(cursor=None) is None

    def test_cache_key_differs_per_cursor(self, tmp_path: Path) -> None:
        client = RegistryClient(cache_dir=tmp_path)
        assert client._cache_key(None) != client._cache_key("a/b:1.0.0")
        assert client._cache_path(None) != client._cache_path("a/b:1.0.0")


# ---------- Unit test on the page-size and base configuration defaults ----------


def test_defaults_match_documented_envelope() -> None:
    client = RegistryClient()
    assert client.api_base == "https://registry.modelcontextprotocol.io"
    assert client.list_path == "/v0/servers"
    assert client.page_size == DEFAULT_PAGE_SIZE


# ---------- Integration test (opt-in via env var) ----------


@pytest.mark.skipif(
    not integration_tests_enabled(),
    reason="Set MCP_VERIFIED_INTEGRATION_TESTS=1 to enable network calls",
)
class TestRegistryClientNetwork:
    def test_fetches_real_inventory_page(self, tmp_path: Path) -> None:
        client = RegistryClient(cache_dir=tmp_path, page_size=5)
        page = client._fetch_page(cursor=None)
        entries, _ = parse_response(page)
        assert len(entries) >= 1
        # At least one entry on the first page should be GitHub-backed in the
        # current registry; if this assertion ever breaks, investigate before
        # weakening it — the assumption is load-bearing for Phase 1.
        assert any(e.is_github_source for e in entries)
