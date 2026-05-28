"""Official MCP registry client.

Implements T-02 / AC-1.2 / AC-4.4.

Fetches the public server inventory from
`https://registry.modelcontextprotocol.io/v0/servers`, parses the documented
JSON envelope, and exposes it as a list of `RegistryEntry` records.

Network surface (AC-4.4 default code path allowlist):
    https://registry.modelcontextprotocol.io/*

The full API discovery + fixture provenance lives at
`docs/evidence/2026-05-28-registry-api-discovery.md` and is the authoritative
source for the field set below.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API_BASE = "https://registry.modelcontextprotocol.io"
LIST_PATH = "/v0/servers"
DEFAULT_PAGE_SIZE = 50
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
USER_AGENT = "mcp-verified/0.0.1 (+https://github.com/leagames0221-sys/mcp-verified)"


@dataclass(frozen=True)
class RegistryEntry:
    """One row from the registry inventory.

    Only the subset of fields used downstream is captured. Forward-compatible:
    unknown fields are kept under `raw` so a future schema bump does not lose
    data and so the client can be diffed against the upstream schema later.
    """

    name: str
    version: str
    description: str
    title: str | None
    repository_url: str | None
    repository_source: str | None
    remotes: tuple[dict[str, str], ...]
    status: str
    is_latest: bool
    published_at: str
    updated_at: str
    raw: dict[str, Any] = field(repr=False)

    @property
    def is_github_source(self) -> bool:
        """True when the server publishes its source on GitHub (AC-1.3 gate)."""
        return (
            self.repository_source == "github"
            and self.repository_url is not None
            and self.repository_url.startswith("https://github.com/")
        )


def _parse_entry(envelope: dict[str, Any]) -> RegistryEntry | None:
    """Parse one `{"server": ..., "_meta": ...}` envelope.

    Returns None if the envelope is malformed enough that we cannot safely
    construct a RegistryEntry. This is a forward-compatibility choice: a
    future schema generation may add required fields we do not yet know
    about, and we prefer skipping a row over crashing the whole walk.
    """
    server = envelope.get("server")
    if not isinstance(server, dict):
        return None
    name = server.get("name")
    version = server.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        return None

    meta = envelope.get("_meta", {})
    official = meta.get("io.modelcontextprotocol.registry/official", {})

    repository = server.get("repository") or {}
    remotes_raw = server.get("remotes") or []
    remotes: list[dict[str, str]] = []
    for r in remotes_raw:
        if isinstance(r, dict) and isinstance(r.get("type"), str) and isinstance(r.get("url"), str):
            remotes.append({"type": r["type"], "url": r["url"]})

    return RegistryEntry(
        name=name,
        version=version,
        description=server.get("description", "") or "",
        title=server.get("title"),
        repository_url=repository.get("url") if isinstance(repository, dict) else None,
        repository_source=repository.get("source") if isinstance(repository, dict) else None,
        remotes=tuple(remotes),
        status=official.get("status", "unknown"),
        is_latest=bool(official.get("isLatest", False)),
        published_at=official.get("publishedAt", ""),
        updated_at=official.get("updatedAt", ""),
        raw=envelope,
    )


def parse_response(payload: dict[str, Any]) -> tuple[list[RegistryEntry], str | None]:
    """Parse a single registry response page.

    Returns `(entries, next_cursor)` where `next_cursor` is None at end-of-walk.
    """
    if not isinstance(payload, dict):
        raise ValueError("registry response is not a JSON object")
    servers = payload.get("servers", [])
    if not isinstance(servers, list):
        raise ValueError("registry response 'servers' field is not a list")
    entries: list[RegistryEntry] = []
    for envelope in servers:
        if isinstance(envelope, dict):
            entry = _parse_entry(envelope)
            if entry is not None:
                entries.append(entry)
    metadata = payload.get("metadata") or {}
    next_cursor = metadata.get("nextCursor") if isinstance(metadata, dict) else None
    if not isinstance(next_cursor, str) or not next_cursor:
        next_cursor = None
    return entries, next_cursor


class RegistryClient:
    """HTTP client for the official MCP registry.

    Reads-only. Uses stdlib `urllib` to avoid a runtime dependency (AC-4.2).

    Caching: responses are written to `<cache_dir>/registry-<sha256>.json`
    where the SHA is over `(API_BASE, LIST_PATH, page_size, cursor)`. Cache
    hits are returned if their `mtime` is within `cache_ttl_seconds`.
    Default `cache_dir` is `~/.cache/mcp-verified/`.
    """

    def __init__(
        self,
        api_base: str = API_BASE,
        list_path: str = LIST_PATH,
        page_size: int = DEFAULT_PAGE_SIZE,
        cache_dir: Path | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        user_agent: str = USER_AGENT,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.list_path = list_path
        self.page_size = page_size
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "mcp-verified")
        self.cache_ttl_seconds = cache_ttl_seconds
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def _cache_key(self, cursor: str | None) -> str:
        material = f"{self.api_base}|{self.list_path}|{self.page_size}|{cursor or ''}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _cache_path(self, cursor: str | None) -> Path:
        return self.cache_dir / f"registry-{self._cache_key(cursor)}.json"

    def _load_cache(self, cursor: str | None) -> dict[str, Any] | None:
        path = self._cache_path(cursor)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.cache_ttl_seconds:
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_cache(self, cursor: str | None, payload: dict[str, Any]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with self._cache_path(cursor).open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except OSError:
            # Caching is best-effort; never fail the call because the cache
            # directory is read-only or full.
            pass

    def _fetch_page(self, cursor: str | None) -> dict[str, Any]:
        cached = self._load_cache(cursor)
        if cached is not None:
            return cached

        params: dict[str, str] = {"limit": str(self.page_size)}
        if cursor:
            params["cursor"] = cursor
        url = f"{self.api_base}{self.list_path}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            payload = json.load(resp)
        if not isinstance(payload, dict):
            raise ValueError("registry response is not a JSON object")
        self._save_cache(cursor, payload)
        return payload

    def list_servers(self, max_pages: int = 100) -> list[RegistryEntry]:
        """Walk the registry inventory, returning every entry across all pages.

        `max_pages` is a safety brake against runaway pagination; the default
        100 pages × 50 entries = 5000 entries is well above the 2026-05 inventory.
        """
        entries: list[RegistryEntry] = []
        cursor: str | None = None
        for _ in range(max_pages):
            payload = self._fetch_page(cursor)
            page_entries, next_cursor = parse_response(payload)
            entries.extend(page_entries)
            if not next_cursor:
                break
            cursor = next_cursor
        return entries

    def list_github_latest(self) -> list[RegistryEntry]:
        """Convenience: only `isLatest == true` entries whose source is GitHub.

        This is the Phase 1 candidate pool (per ADR-002 + ADR-003).
        """
        return [e for e in self.list_servers() if e.is_latest and e.is_github_source]


def integration_tests_enabled() -> bool:
    """Test-suite gate: opt-in network calls for integration tests."""
    return os.environ.get("MCP_VERIFIED_INTEGRATION_TESTS") == "1"
