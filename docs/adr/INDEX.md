# Architecture Decision Records

Nygard-format ADRs. Each record has four canonical sections: **Status**, **Context**, **Decision**, **Consequences**.

| # | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-stack-python-311.md) | Stack: Python 3.11+ on hatchling, sibling-consistent with session-eval | Accepted |
| [ADR-002](ADR-002-registry-data-source.md) | Registry data source: official `registry.modelcontextprotocol.io` only for Phase 1 | Accepted |
| [ADR-003](ADR-003-read-only-static-analysis.md) | Candidate handling: read-only static analysis, never execute candidate code | Accepted |
| [ADR-004](ADR-004-ollama-default-provider.md) | Default LLM provider: Ollama `gemma3:4b` at temperature 0 with structured output | Accepted |
| [ADR-005](ADR-005-audit-db-schema-compat.md) | Output schema: compatible with Cloud Security Alliance `audit-db` for Phase 1.5 upstream contribution | Accepted |
| [ADR-006](ADR-006-tier-verdict-naming.md) | Tier verdict naming: `verified` / `caution` / `risky` / `unknown` (plain words, not ordinal stars) | Accepted |
| [ADR-007](ADR-007-mcpserver-audit-checks-fork.md) | Check seed: fork `mcpserver-audit/checks/` under Apache 2.0 with attribution preserved | Accepted |
| [ADR-008](ADR-008-phase1-popularity-signal.md) | Phase 1 popularity signal: registry recency only (GitHub-stars enrichment deferred to Phase 1.5) | Accepted |
| [ADR-009](ADR-009-pyyaml-runtime-dependency.md) | Phase 1 frontmatter parser: hand-rolled minimal subset, zero runtime deps | Accepted |
| [ADR-010](ADR-010-sandbox-doctrine-for-future-stdio-probes.md) | Sandbox doctrine for any future stdio-probe stage | Accepted |
| [ADR-011](ADR-011-mcp-protocol-threat-taxonomy-adoption.md) | Adopt MCP-protocol threat taxonomies as design inspiration, not as a sealed check schema | Accepted |
| [ADR-012](ADR-012-schema-hash-diff-for-rug-pull-detection.md) | Schema-hash diff as the canonical detection signal for the "rug-pull" tool-mutation class | Accepted |
