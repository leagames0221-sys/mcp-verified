# mcp-verified

Reproducible, batched audit of every server in the official MCP registry, run under strict zero-cost, zero-credential, local-first, security-first constraints. Produces a queryable verdict registry with per-server evidence path, AIVSS-aligned scoring, and Ollama-only deep-review reproducibility.

> Status: **early development (PRIVATE repo)**. Public release pending Phase 1.5 dogfood verify + portfolio quality gate.

## Why this exists

**Motivation.** MCP servers are being wired into agents faster than anyone is auditing them. The threat figures that circulate in blog posts (e.g. the Equixly "43% command injection / 22% path traversal / 30% SSRF") did not survive primary-source verification in our 2026-05-29 deep-research probe — the underlying post publishes no sample size or methodology. Meanwhile Li and Gao (arXiv:2510.16558, accepted to DSN 2026) catalogued 67,057 servers, yet there is still no *reproducible, per-server* verdict registry that a non-expert can re-run for free. That gap is what this project targets.

**Approach.** The design is driven by four hard constraints — free, no credit card, local-first, security-first — and most of the non-obvious decisions fall out of taking them literally:

- audited source is cloned **read-only and never executed** ([ADR-003](docs/adr/ADR-003-read-only-static-analysis.md));
- the default deep-review provider is **local Ollama**, with cloud providers opt-in behind an env var ([ADR-004](docs/adr/ADR-004-ollama-default-provider.md));
- output is **schema-compatible with the CSA `audit-db`** so verdicts are portable rather than locked in ([ADR-005](docs/adr/ADR-005-audit-db-schema-compat.md));
- the check set is **forked from `mcpserver-audit`** rather than reinvented, with attribution pinned to an upstream commit ([ADR-007](docs/adr/ADR-007-mcpserver-audit-checks-fork.md));
- the package ships **zero runtime PyPI dependencies**, down to a hand-rolled frontmatter parser instead of pulling in PyYAML ([ADR-009](docs/adr/ADR-009-pyyaml-runtime-dependency.md)).

**Result.** Phase 1 is source-complete: 284 tests, 89.8% line coverage (measured with a stdlib-only coverage script), 12 ADRs, 16 checks (4 forked verbatim + MCP-specific extensions), and 0 runtime dependencies. Dogfood probes are recorded under [`docs/evidence/`](docs/evidence/). What is **not** done yet is stated plainly under [Limitations](#limitations): the LLM-vs-deterministic F1 measurement and the Top-50 live-registry pilot are deferred to Phase 1.5. The clearest lesson: the four constraints, treated as non-negotiable, drove more of the design than any feature list would have — and "verify the headline numbers yourself" had to become a project value rather than an afterthought.

## What it does

1. **Registry-wide batched audit pipeline** — Walks the official MCP registry, performs read-only static analysis on each server's source repository (no `npm install`, no code execution), runs a modular set of security checks, and emits a per-server verdict.
2. **Queryable verdict registry** — Each audited server gets a deterministic directory under `audits/<host>/<owner>/<repo>/audits/<auditor>-<date>-<NNN>/`, containing a top-level `security-assessment.md`, per-finding markdown files, and a machine-readable `audit-manifest.json`. The schema is compatible with the Cloud Security Alliance `audit-db` project.
3. **Ollama-only deep-review reproducibility** — Anyone with Ollama installed can replay the audit and reproduce the same verdict, with no paid API and no credential setup.

## Demo

![mcp-verified quickstart — auditing three servers from a fixture registry with `--provider mock`, then reading the generated per-server `security-assessment.md` (verdict: risky, 28 high-severity findings).](docs/demo/quickstart.png)

The walkthrough above runs offline against a bundled fixture (`--provider mock`, no network, no code execution). The raw CLI captures are under [`docs/demo/cli/`](docs/demo/cli/) and a full sample verdict tree under [`docs/demo/sample-audit/`](docs/demo/sample-audit/); the image is rendered from that real output by [`scripts/render_demo.py`](scripts/render_demo.py).

## Four constraints (cross-cutting)

- **Free** — Only OSS dependencies (MIT / Apache 2.0 / BSD / ISC). No paid services in the default flow.
- **No credit card** — Default provider is Ollama (local). Cloud providers are optional and require the user's own key.
- **Local-first** — Deep code review uses `http://localhost:11434` by default. Cloud providers are opt-in via environment variable, never default.
- **Security-first** — `gitleaks` + path-leak guard + license audit run as pre-commit hooks. Untrusted server source is cloned read-only and analyzed statically; no candidate code is ever executed.

## Sibling repo

This project is a sibling of [`mcp-guard`](https://github.com/leagames0221-sys/mcp-guard), an MCP-configuration scanner for individual developers and SMBs. The two together cover MCP defense-in-depth from two directions:

- `mcp-guard` — single-config, developer-side, pre-deployment scan of `.mcp.json`
- `mcp-verified` — registry-wide, consumer-side, pre-adoption audit of every published server

## Quickstart

A five-command, no-Ollama-required walkthrough is at
[`examples/quickstart.md`](examples/quickstart.md). The short form:

```bash
git clone https://github.com/leagames0221-sys/mcp-verified
cd mcp-verified
pip install -e ".[dev]"
mcp-verified audit \
    --fixture tests/fixtures/registry-snapshot-2026-05-28.json \
    --top 3 --provider mock --out my-audit
cat my-audit/audits/github.com/*/*/audits/*/security-assessment.md
```

For the live registry, drop `--fixture` and optionally
`ollama pull gemma3:4b` if you want LLM-assisted checks.

Recorded CLI captures and a sample verdict registry tree live under
[`docs/demo/`](docs/demo/).

## Limitations

- Phase 1 covers servers whose source is published on GitHub (84.6% of registry entries per the public-source-publication rate observed in February 2026). Servers with no public source are reported as `unknown` with no further analysis.
- Read-only static analysis only. Dynamic vulnerabilities that require execution (race conditions, runtime injection) are out of scope for Phase 1.
- Tier verdicts are reproducibility-stable, not "correctness" claims. A `verified` verdict means the server passed the published check set, not that no vulnerability exists.
- Phase 1 audits a curated subset (top 50 by popularity) rather than the full registry. Full-registry coverage is deferred to Phase 2 pending throughput probe results.
- `mcp-verified` does **not** claim "covers the CSA `mcpserver-audit` six-category taxonomy" or "implements the `mcp-scan` matrix" in full. Both upstream taxonomies are adopted as design inspiration; per-check coverage is declared in each check's `aliases` frontmatter block per [ADR-011](docs/adr/ADR-011-mcp-protocol-threat-taxonomy-adoption.md). A reviewer assembling a coverage matrix from those declarations will find genuine gaps; we name them rather than over-claim.
- Rug-pull detection ships in Phase 1 only as a **static precondition** — flagging servers whose source-level tool-definition construction depends on runtime-mutable state. The full dynamic detection signal (schema-hash diff across `tools/list` samples per [ADR-012](docs/adr/ADR-012-schema-hash-diff-for-rug-pull-detection.md)) requires the sandboxed dynamic-probe stage governed by [ADR-010](docs/adr/ADR-010-sandbox-doctrine-for-future-stdio-probes.md) and is not shipped in Phase 1.
- The widely-cited Equixly figures (43% command injection / 22% path traversal / 30% SSRF among tested MCP servers) did not survive independent verification in our deep-research probe of 2026-05-29 (see [`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`](docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md)); the primary source is a single blog post with no published sample size or methodology. `mcp-verified` does not cite these figures, and intends the Phase 1.5 Top-50 pilot to publish the first defensible numerator-and-denominator measurement for these questions on the official MCP registry.

## Architecture

- `docs/adr/` — Nygard-format architecture decision records.
- `docs/evidence/` — Primary source fetches preserved as audit evidence.
- `checks/` — Modular vulnerability checks, seeded from [`mcpserver-audit`](https://github.com/ModelContextProtocol-Security/mcpserver-audit) (Apache 2.0, attribution preserved per `checks/ATTRIBUTION.md`).
- `audits/` — Per-server verdict output, schema-compatible with [`audit-db`](https://github.com/ModelContextProtocol-Security/audit-db).

## Acknowledgments

- Vulnerability check templates adapted from [`mcpserver-audit`](https://github.com/ModelContextProtocol-Security/mcpserver-audit), a Cloud Security Alliance community project (Apache 2.0).
- Output schema follows [`audit-db`](https://github.com/ModelContextProtocol-Security/audit-db) (Apache 2.0).
- Scoring backbone aligns with the AIVSS (AI Vulnerability Scoring System) framework published by the CSA MCP Security Project.
- Threat model informed by Li and Gao, "A First Look at the Security Issues in the Model Context Protocol Ecosystem" (arXiv:2510.16558, accepted to DSN 2026).

## License

[MIT](LICENSE)
