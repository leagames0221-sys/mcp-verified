# Evidence files

Primary-source fetches and verification trails are persisted here so that future audit runs do not re-fetch the same data and so that any verdict can be traced back to the source it was built on.

| # | Date | Topic | File |
|---|---|---|---|
| 1 | 2026-05-28 | Official MCP registry API discovery | [`2026-05-28-registry-api-discovery.md`](2026-05-28-registry-api-discovery.md) |
| 2 | 2026-05-29 | Registry has no popularity signal (probe) | [`2026-05-29-registry-no-popularity-signal-probe.md`](2026-05-29-registry-no-popularity-signal-probe.md) |
| 3 | 2026-05-29 | Dogfood probes B1/B2/B4 (Phase 1 pilot) | [`2026-05-29-dogfood-probes.md`](2026-05-29-dogfood-probes.md) |
| 4 | 2026-05-29 | Deep-research MCP threat-surface probe | [`2026-05-29-deep-research-mcp-threat-surface.md`](2026-05-29-deep-research-mcp-threat-surface.md) |
| 5 | 2026-05-29 | Citation verification (arXiv:2510.16558, earezki, Equixly) | [`2026-05-29-citation-verification.md`](2026-05-29-citation-verification.md) |

## Conventions

- One file per primary source per fetch date.
- Filename: `<YYYY-MM-DD>-<short-slug>.md` (e.g., `2026-06-01-registry-api-discovery.md`).
- Frontmatter declares the source URL, fetch timestamp, fetcher (human or tool), and license / terms-of-use note.
- The body is the literal extracted content (truncated only if oversized, with the truncation point noted).
- Subsequent reverifications append rather than overwrite.
