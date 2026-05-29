# ADR-002 — Registry data source: official registry only for Phase 1

## Status

Accepted, 2026-05-28.

## Context

The MCP ecosystem has multiple registries as of 2026-05. Li and Gao (arXiv:2510.16558, accepted to DSN 2026) catalogued 67,057 servers across six registries:

- Centralized: `registry.modelcontextprotocol.io` (official, ~518+ entries in Feb 2026), Smithery, npm.
- Decentralized: `mcp.so`, MCP Market, MCP Store, Pulse MCP.

Phase 1 must choose a source. Considerations:

- The official registry is the canonical reference, has a documented submission process, and is the most widely cited in security research.
- The decentralized registries together cover ~10× more servers but have no unified schema, no submission gates, and unclear data licenses.
- Cross-registry coverage adds engineering surface (per-registry adapters, deduplication, schema normalization) that is not justified by Phase 1's strong-hire signal goal.

## Decision

For **Phase 1**, the only data source is **`registry.modelcontextprotocol.io`**. Phase 1 will:

1. Resolve the registry's public list endpoint (currently under documentation; the resolved endpoint is recorded under `docs/evidence/` once probed).
2. Cache the inventory locally with a documented TTL.
3. Operate only on entries whose published `repository_url` is on GitHub (~84.6% of the inventory per the public-source-publication rate from earezki, 2026-02).
4. Defer all non-GitHub and non-official-registry entries to a Phase ≥ 2 backlog.

## Consequences

**Positive**:

- Single registry adapter, single popularity signal, single submission gate to reason about.
- Strongest citation strength: the official registry is the de-facto reference for security research output.
- Easy to communicate scope: "every server in the official registry, GitHub-published, audited."

**Negative**:

- Phase 1 misses ~15% of registry entries (non-GitHub-published) and a much larger long tail in decentralized registries.
- A reviewer who expects "all MCP servers" coverage will see "official-registry, GitHub-published, top-50" — Limitations section in `README.md` and out-of-scope list in `spec.md` § 5 acknowledge this honestly (NFR-5).

**Neutral**:

- Cross-registry adapter design can be added in Phase 4 (continuous re-audit + expanded coverage) without invalidating Phase 1 module boundaries.
