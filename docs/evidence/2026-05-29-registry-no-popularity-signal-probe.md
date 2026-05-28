---
source_url: https://registry.modelcontextprotocol.io/v0/servers?limit=10
fetch_date: 2026-05-29
fetcher: human + curl + python introspection
license_note: Same terms as the earlier 2026-05-28 fetch.
---

# Registry popularity-signal probe

## Question

Does the official MCP registry response include any signal that can directly proxy popularity (download count, star count, install count, dependent count, view count, etc.)?

## Method

Fetched `GET /v0/servers?limit=10` and enumerated the union of keys present in any record under `server.*` and `_meta.*`. For each record, also checked whether the optional fields `packages`, `repository`, and `remotes` are present.

## Result — server-envelope keys (union across 10 entries)

```
$schema, _meta, description, icons, name, remotes, repository, title, version, websiteUrl
```

## Result — `_meta` keys (union across 10 entries)

```
io.modelcontextprotocol.registry/official
io.modelcontextprotocol.registry/official.isLatest
io.modelcontextprotocol.registry/official.publishedAt
io.modelcontextprotocol.registry/official.status
io.modelcontextprotocol.registry/official.statusChangedAt
io.modelcontextprotocol.registry/official.updatedAt
```

## Result — optional-field presence (10 entries)

| name | packages | repository | remotes |
|---|---|---|---|
| `ac.inference.sh/mcp` (v1.0.0) | ❌ | ❌ | ✅ |
| `ac.inference.sh/mcp` (v1.0.1) | ❌ | ❌ | ✅ |
| `ac.tandem/docs-mcp` (×3) | ❌ | ✅ | ✅ |
| `agency.lona/trading` | ❌ | ✅ | ✅ |
| `ai.31st/mcp` | ❌ | ❌ | ✅ |
| `ai.aarna/atars-mcp` | ❌ | ❌ | ✅ |
| `ai.abmeter/abmeter` | ❌ | ✅ | ✅ |
| `ai.adadvisor/mcp-server` | ❌ | ❌ | ✅ |

## Conclusion

The registry response carries **no popularity signal** — no downloads, no stars, no installs, no dependents. The only ranking-eligible fields are:

- `_meta.io.modelcontextprotocol.registry/official.publishedAt` — when this version was published.
- `_meta.io.modelcontextprotocol.registry/official.updatedAt` — when this record was last updated.
- `_meta.io.modelcontextprotocol.registry/official.status` — `"active"` observed; other values are documented but not present in this sample.
- `_meta.io.modelcontextprotocol.registry/official.isLatest` — version dedup.

`packages` (which could expose npm / PyPI namespaces and enable an external download lookup) is **empty across all 10 sampled entries**. The first-page sample does not contain any `packages`-bearing record.

## Implication for Phase 1 popularity scoring (T-03)

The TASKS.md T-03 draft formula `GitHub stars × log10(downloads) with a freshness penalty` is **not implementable from registry data alone**. Realizing it requires:

- A GitHub API call per candidate to fetch stargazers count (network surface bump within the AC-4.4 allowlist, but a real second outbound endpoint).
- An npm / PyPI API call per candidate that carries a `packages` entry (also within the allowlist by domain pattern, but additional surface).

For Phase 1's strong-hire signal goal, the trade-off is:

- **Adopt registry-recency-only scoring** (deterministic, no extra network, no rate-limit risk) and disclose the limitation in the docstring / ADR honestly.
- **Or bring in GitHub API enrichment now** (more accurate signal, more surface, more failure modes including rate limits without auth, more test fixtures).

[ADR-008](../adr/ADR-008-phase1-popularity-signal.md) records the decision to take the first path for Phase 1 and defer GitHub API enrichment to Phase 1.5 or later.
