# ADR-007 — Check seed: fork `mcpserver-audit/checks/` with attribution

## Status

Accepted, 2026-05-28.

## Context

The check definitions are the central asset: each `checks/<name>.md` describes one vulnerability category, with detection guidance, severity, CWE mapping, and good/bad code examples.

Options considered:

- **Zero-generation** — write all check definitions from scratch.
- **Fork upstream** — start from an existing curated check set and extend.

[`mcpserver-audit`](https://github.com/ModelContextProtocol-Security/mcpserver-audit), a Cloud Security Alliance community project under Apache 2.0, ships 14 markdown checks with a consistent Obsidian-style frontmatter and a standard five-section structure (CWE tag, AI instructions, human assessment steps, risk evaluation, good/bad examples). Inventory at the time of writing:

- `credential-management-security.md` (CWE-798, 200, 522)
- `docker-security.md`
- `compose-security.md`
- `ci-secrets.md`
- `k8s-security.md`
- `http-client-resilience.md`
- `advanced-obfuscation-evasion-security-check.md`
- `dynamic-content-execution-security-check.md`
- `network-port-binding-security-check.md`
- `python-authentication-semgrep-security-check.md`
- `README-python-authentication-semgrep-security-check.md`
- `main-prompt.md` (framework)
- `CHECK-TEMPLATE.md` (template)
- `README.md` (overview)

Fit estimate: ~70% — the structure is reusable verbatim; some checks need MCP-specific extension (e.g., MCP transport, tool poisoning patterns from arXiv 2510.16558).

Apache 2.0 is permissive and MIT-compatible for distribution; attribution must be preserved per the license.

## Decision

Fork the upstream `mcpserver-audit/checks/` into `checks/` of this repository, preserving:

- The five-section structure of each markdown check.
- The Obsidian-style frontmatter including CWE tags.
- A top-level `checks/ATTRIBUTION.md` recording the upstream commit hash forked from, the Apache 2.0 license terms, and the date of fork.

Local extensions:

- Add MCP-specific checks (`mcp-transport-security.md`, `tool-poisoning-detection.md`, `redirect-hijacking.md`) modeled on the attack taxonomy in arXiv 2510.16558.
- Refactor `main-prompt.md` to fit the `mcp-verified` LLM-assisted check executor's structured-output schema; the original framework remains attributed.

## Consequences

**Positive**:

- Phase 1 starts with 14 working check definitions instead of zero.
- Upstream improvements (new check categories, refined detection guidance) can be tracked and pulled in periodically.
- Prior-art-first scanning is honored: ~70% fit upstream beats from-scratch generation that would carry hidden debt.

**Negative**:

- Inheriting upstream defects: any imprecision in a forked check propagates to our verdicts until we audit and refine.
- Attribution-tracking discipline: every external contribution must check upstream commit hash and bump `checks/ATTRIBUTION.md` if the source files change.

**Neutral**:

- License compatibility: Apache 2.0 → MIT distribution carries attribution requirements but no copyleft; no impact on downstream consumers.
