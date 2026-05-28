# ADR-009 — Phase 1 frontmatter parser: hand-rolled minimal subset, zero runtime deps

## Status

Accepted, 2026-05-29.

## Context

T-05 (`mcp_verified/checks/loader.py`) parses check-definition files whose frontmatter is YAML, in the convention used by the upstream `mcpserver-audit` project. The probe of a real upstream check (`credential-management-security.md`, recorded under `docs/evidence/`) confirmed the schema is small and uniform:

```yaml
---
title: MCP Server Credential Management Security Check
version: 1.0
date: 2025-08-07
tags: [security, credentials, secrets, environment-variables, MCP]
aliases: [secrets-management, credential-security]
status: active
priority: critical
cwe: [798, 200, 522]
cwe-primary: 798
vulnerability-db: []
---
```

The shapes observed across the upstream fork are:

- `key: scalar` where scalar is a string, integer, or version-like token.
- `key: [item, item, item]` inline list of strings or integers.
- `key: []` empty list.

No block-style lists, no multi-line strings, no anchors / aliases, no nested maps in the frontmatter. The schema is small enough to parse without a general YAML library.

Options considered:

- **Hand-rolled minimal frontmatter parser.** Zero runtime dependency. Schema-locked to the small subset above; raises explicitly on anything else (no silent acceptance of unknown shapes). ~80 LoC including tests.
- **PyYAML (MIT, ~20-year vintage).** Battle-tested general YAML. Would be safe in principle (`safe_load`-only invariant possible), but adopts one supply-chain edge for parsing a schema we own and can keep small.
- **`ruamel.yaml`.** Same trade-off as PyYAML with more API surface.
- **Switch frontmatter format to TOML.** Stdlib `tomllib` available in Python 3.11+. Breaks compatibility with the upstream `mcpserver-audit` convention which is the seed source per ADR-007.

The supply-chain security gate enforced by this project's harness explicitly favors "zero new edge" when the schema is small enough to control. The Phase 1 schema is small enough.

## Decision

Phase 1 ships a **hand-rolled minimal frontmatter parser** under `mcp_verified/checks/frontmatter.py`. The parser:

- Accepts the `---\n<YAML>\n---\n<body>` envelope. Refuses files that do not start with the `---` marker.
- Within the YAML block, accepts exactly one line per key: `^\s*([A-Za-z][\w-]*)\s*:\s*(.+?)\s*$`.
- Scalar values resolve to: `int` if entirely digits; `float` if matches `^\d+\.\d+$`; `bool` if literal `true`/`false`; otherwise stripped string.
- List values resolve to: `[a, b, c]` parsed by splitting on commas after stripping the outer `[`/`]`. Empty list `[]` returns `[]`.
- Quoted strings (`"..."` or `'...'`) have their quotes stripped.
- Anything else — block lists, anchors, multi-line strings, nested maps — raises `FrontmatterParseError` explicitly. Future upstream schema extensions will fail loud, not silent.

`pyproject.toml` declares **zero runtime dependencies** for Phase 1. AC-4.3 is honored without a new exception.

## Consequences

**Positive**:

- Zero supply-chain edges added. The dependency tree at install time is exactly Python stdlib.
- Parser surface is ~80 LoC and unit-testable in isolation; the entire grammar fits in one screen.
- Explicit-failure-on-unknown-shape is more honest than a permissive parser that silently accepts shapes the check loader downstream does not actually handle.
- The supply-chain security gate enforced by the harness (which blocks ad-hoc `pip install`) is not in conflict with the Phase 1 toolchain.

**Negative**:

- Upstream `mcpserver-audit` could introduce a frontmatter shape we do not yet support (block list, multi-line string). When that happens, we either extend the parser explicitly with a new shape rule + ADR amendment, or adopt PyYAML at that point. Either path is taken consciously, not silently.
- The hand-rolled parser is one more piece of code that we own and must maintain. The maintenance cost is bounded by the schema surface area, which is small.

**Neutral**:

- If a future module elsewhere in the project needs a general YAML parser, this ADR is revisited and `pyyaml>=6.0` is added with a separate ADR. Phase 1 does not need that today.
