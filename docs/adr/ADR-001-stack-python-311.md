# ADR-001 — Stack: Python 3.11+ on hatchling

## Status

Accepted, 2026-05-28.

## Context

`mcp-verified` is the second portfolio tool in a three-tool series:

1. `mcp-guard` — single-config MCP scanner, TypeScript on Node.js 20.
2. `session-eval` — within-session LLM degradation detector + local-LLM judge benchmark, Python 3.11+.
3. `mcp-verified` — this project, registry-wide MCP server audit + verdict registry.

The implementation language affects: (a) reuse of infrastructure already invested in a sibling, (b) ecosystem fit for batched orchestration and audit scripting, (c) the polyglot vs. monoglot story the portfolio presents to a reviewer.

Three options were considered:

- **TypeScript on Node.js 20** — reuses `mcp-guard` sibling pattern verbatim (pnpm + vitest + commander + zod + pre-commit chain). The MCP ecosystem itself is Node-heavy at the protocol layer.
- **Python 3.11+ on hatchling** — reuses `session-eval` infrastructure (provider ABC, `pyproject.toml` shape, `pre-commit-config.yaml`, `scripts/private_path_check.sh`, `scripts/audit_deps.py`). AIVSS reference implementations are Python-first; arXiv 2510.16558 reproducibility tooling is Python; audit scripting / batch orchestration plays to Python's strengths.
- **Rust** — strongest performance, weakest reuse (no sibling at all), highest onboarding cost for any reviewer cloning the repo.

## Decision

Use **Python 3.11+ with hatchling build backend**, mirroring the `session-eval` skeleton.

Specifically:

- `pyproject.toml` declares `requires-python = ">=3.11"`, MIT license, hatchling build.
- Zero runtime dependencies in the v0.0.1 baseline; each future addition is justified by an ADR (per AC-4.3).
- Optional `[project.optional-dependencies] dev = [pytest, pytest-cov, ruff, pre-commit]`.
- CLI entry point `mcp-verified = "mcp_verified.cli:main"`.

## Consequences

**Positive**:

- Direct reuse of `session-eval` artifacts: `scripts/audit_deps.py`, `scripts/private_path_check.sh`, the pre-commit chain, the provider ABC pattern, the CI workflow shape.
- Ollama Python client is the canonical local-LLM binding; LLM-assisted check execution is straightforward.
- AIVSS reference and arXiv 2510.16558 attack taxonomy are easy to lift directly into Python check definitions.
- Polyglot portfolio (TS + Python) reads as "appropriate tool selection per problem domain" rather than language-lock.

**Negative**:

- Two-language portfolio means a reviewer cannot run a single toolchain across the three projects; this is mitigated by README quickstart commands being copy-paste-runnable on either toolchain.
- Python startup latency is higher than Node.js; for a tool that runs N=50 audits in a single invocation, per-process startup is amortized and acceptable.

**Neutral**:

- Cross-platform support: Windows 11 (primary), Linux (CI), macOS (best-effort) — same as `session-eval`.
