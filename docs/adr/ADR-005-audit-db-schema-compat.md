# ADR-005 — Output schema: compatible with CSA `audit-db`

## Status

Accepted, 2026-05-28.

## Context

`mcp-verified` produces per-server verdicts. The output format determines whether those verdicts are consumable downstream.

Two paths considered:

- **Custom schema** — design our own JSON / markdown layout for verdicts.
- **`audit-db` schema** — follow the layout defined by the Cloud Security Alliance MCP Security project's `audit-db` repository.

The `audit-db` project ([github.com/ModelContextProtocol-Security/audit-db](https://github.com/ModelContextProtocol-Security/audit-db)) is the upstream community database for MCP server audit findings. It defines:

- Directory layout: `audits/<host>/<owner>/<repo>/audits/<auditor>-<date>-<NNN>/`.
- Per-server: `security-assessment.md`, `findings/<severity>-<NNN>-<slug>.md`, `metadata.json`.
- Manifest: `audit-manifest.json` with fields `audit_id`, `auditor`, `target`, `audit_metadata`, `findings_summary`, `tools_used`, `compliance_checks`.
- Submission process: PR-based, with `tools/validate-audit.py` enforcing schema.
- License: Apache 2.0.

Adoption is currently small (9 commits, 10 stars at the time of writing), but the project is positioned as the canonical submission target for the CSA MCP Security initiative.

## Decision

`mcp-verified` Phase 1 writes output in the **`audit-db` schema verbatim**.

Specifically:

- `output/manifest.py` produces `audit-manifest.json` whose field set is byte-compatible with the upstream definition pinned in this ADR.
- `output/assessment.py` produces `security-assessment.md` with the upstream's section ordering.
- `output/findings.py` produces per-finding markdown files using the upstream naming convention `<severity>-<NNN>-<slug>.md`.
- `output/exporter.py` provides `mcp-verified export-audit-db <repo>`, which emits a tarball laid out exactly as expected by an `audit-db` pull request (AC-6.3).

The pinned upstream version is recorded in this ADR's amendments section; bumps require an ADR amendment plus CI surfacing the schema diff (AC-6.2).

## Consequences

**Positive**:

- Phase 1.5 can submit 5–10 verdicts upstream as `audit-db` pull requests with zero schema-translation cost.
- Downstream consumers of `audit-db` (organizations evaluating MCP servers using the CSA database) get `mcp-verified` output for free.
- Strong-hire signal: visible upstream contribution to a community security project is exactly the "M3 — non-trivial decision with cross-org collaboration" item that the portfolio rubric rewards.

**Negative**:

- We inherit upstream schema decisions, including any that turn out suboptimal for our use case. Mitigation: ADR-006 (tier verdict naming) shows we still own the inside-the-cells values.
- A future breaking change upstream forces a schema bump (AC-6.2 handles surfacing it; the bump itself requires owner action).

**Neutral**:

- Schema is a thin layer; ~95% of `mcp-verified` engineering is upstream-independent.
