---
source_url: https://registry.modelcontextprotocol.io/v0/servers
fetch_date: 2026-05-28
fetcher: human + curl
license_note: Registry data license not declared at endpoint. Treat as public-facing metadata; no redistribution restriction observed. Schema documents itself as auto-generated from the upstream OpenAPI spec.
---

# Official MCP Registry — API discovery

## Endpoint

```
GET https://registry.modelcontextprotocol.io/v0/servers?limit=N
```

- HTTP 200, ~450 bytes per server entry (median, observed against the first three records).
- Wall-clock latency: 0.74 s for `limit=2` from a Tokyo consumer connection (single sample).
- `/api/v0/servers` is not the canonical path; it returns HTTP 404. The version segment lives at the path root.

## Response shape

```json
{
  "servers": [
    {
      "server": { "name": "...", "description": "...", "version": "1.0.0", "remotes": [...], "repository": {...} },
      "_meta": { "io.modelcontextprotocol.registry/official": { "status": "active", "publishedAt": "...", "isLatest": false } }
    }
  ],
  "metadata": {
    "nextCursor": "<server.name>:<server.version>",
    "count": 3
  }
}
```

## Per-server `server` fields (observed)

| Field | Type | Notes |
|---|---|---|
| `$schema` | string (URL) | Always `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json` for the current generation. |
| `name` | string | Namespaced identifier, e.g. `ac.inference.sh/mcp` or `ac.tandem/docs-mcp`. |
| `description` | string | Free-form prose. |
| `title` | string | Optional display name. |
| `version` | string | Semver-ish. |
| `repository` | object | **Optional.** Present as `{"url": "https://github.com/...", "source": "github"}` when the server is published from source; absent for remote-only servers. |
| `remotes` | array | Optional. List of `{"type": "streamable-http" \| "sse" \| ..., "url": "..."}` entries for hosted/remote servers. |
| `packages` | array | Documented in the upstream schema for npm/PyPI/Cargo published packages; not observed in the first three results. |

## Per-server `_meta.io.modelcontextprotocol.registry/official` fields

| Field | Type | Notes |
|---|---|---|
| `status` | string | Observed `"active"`. |
| `statusChangedAt` | string (RFC 3339) | Last status mutation timestamp. |
| `publishedAt` | string (RFC 3339) | Publication timestamp of this version. |
| `updatedAt` | string (RFC 3339) | Last record update. |
| `isLatest` | boolean | True for the latest version of a given `name`; false for prior versions. **Multiple records per server name are normal** — the registry retains version history, and the client must dedupe by `(name, isLatest=true)` for current-state queries. |

## Schema reference

`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json` — JSON-Schema draft-07, 22 KB, auto-generated from the upstream OpenAPI specification per the schema's own `$comment` field. Documents the full type tree: `Argument` (positional / named), `Icon`, `Input` (`InputWithVariables`, `KeyValueInput`), `LocalTransport` (`StdioTransport`, `StreamableHttpTransport`, `SseTransport`), and so on. Phase 1 does not validate against the full schema; it consumes the small subset above.

## Implications for the audit pipeline

- **Versioning**: filter for `_meta.io.modelcontextprotocol.registry/official.isLatest == true` when constructing the candidate set; otherwise the same logical server appears multiple times.
- **GitHub gate**: only entries with `server.repository.source == "github"` and a parsable `server.repository.url` matching `https://github.com/<owner>/<repo>` are eligible for Phase 1 audit. Remote-only servers (no `repository`) get verdict `unknown` per AC-1.4.
- **Pagination**: response carries `metadata.nextCursor`. Phase 1 issues `?cursor=<nextCursor>&limit=N` to walk the inventory in batches. The cursor value is `"<server.name>:<server.version>"`.
- **Field stability**: the `$schema` URL pins a date (`2025-12-11`); a future generation may bump the date, and the client should warn rather than fail on unrecognized fields (forward-compatible parse).

## Recorded fixture

`tests/fixtures/registry-snapshot-2026-05-28.json` captures the literal response of `GET /v0/servers?limit=3`, used by `tests/test_registry_client.py` so the test suite remains deterministic without network access.
