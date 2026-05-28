# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-29

Phase 1 source-complete milestone. Twenty-two of twenty-three planned
tasks land; the one remaining task (T-19 GitHub Actions green flag)
is configured and registered but waits on the T-25 PUBLIC visibility
flip to actually run.

### Added

- **Audit pipeline** (T-15 + T-02 + T-03 + T-04 + T-06 + T-09 + T-10).
  `mcp-verified audit` walks the official MCP registry, scores
  candidates by registry-recency, safe-clones each GitHub-published
  source under a per-server wall-clock budget, runs the deterministic
  + LLM-assisted check executors, and writes the verdict registry.
- **Verdict registry** (T-13 + T-11 + T-16). Per-target directory
  tree compatible with the Cloud Security Alliance `audit-db` schema:
  `audits/<host>/<owner>/<repo>/audits/<auditor>-<date>-<NNN>/` with
  `audit-manifest.json`, `security-assessment.md`, and
  `findings/<severity>-<NNN>-<slug>.md`. Verdicts are
  `verified` / `caution` / `risky` / `unknown` per ADR-006.
- **Provider abstraction** (T-07 + T-08). `MockProvider` (default,
  network-free) and `OllamaProvider` (default LLM, `gemma3:4b` at
  temperature 0) plus three paid providers (Anthropic, OpenAI,
  Gemini) that are **refused at runtime** unless
  `MCP_VERIFIED_PAID_PROVIDER_OPT_IN=1` is set, even when the vendor
  API key is in the environment.
- **Check seed** (T-17 + T-05). Seven active check definitions
  under `checks/`: four forked verbatim from upstream
  `mcpserver-audit@8e54ffb77e710bd26009786d93a5df154fa4b45d`
  (Apache 2.0, attribution in `checks/ATTRIBUTION.md`) plus three
  MCP-specific extensions (`mcp-transport-security`,
  `tool-poisoning-detection`, `redirect-hijacking`) modeled on
  arXiv 2510.16558.
- **Divergence detector** (T-12). When the same target is audited
  twice at the same commit and the verdicts disagree, the second run
  writes a `discrepancy.md` alongside the new
  `security-assessment.md`.
- **Tarball exporter** (T-14). `mcp-verified export-audit-db`
  packages one target's audit subtree for upstream PR submission;
  the tarball is byte-deterministic (mtime=0, uid=0, gid=0).
- **CLI** (T-15). Three subcommands: `audit`, `export-audit-db`,
  `version`. End-of-run prints the seven-counter summary line per
  AC-1.7.
- **Test suite** (T-18). 280 unit tests passing; line coverage
  measured at **89.8%** via `scripts/coverage_stdlib.py` (no
  `pytest-cov` install required for the local gate). Coverage gate
  pinned at 80% floor.
- **CI workflows** (T-19). Three workflows under
  `.github/workflows/` (`ci.yml`, `gitleaks.yml`, `secrets-scan.yml`)
  cover an `[ubuntu-latest, windows-latest] x [3.11, 3.12]` matrix
  plus macOS best-effort, gitleaks, and a license-audit redundancy.
  CI runner activation waits on the T-25 PUBLIC flip.
- **Release gate** (T-20). `scripts/release_gate.sh` runs an
  eight-item F-007 / AC-7.1 checklist (tests + coverage + smoke
  audit + customer + internal word-list sweeps + ADR count +
  README LIMITATIONS + SECURITY.md) and exits non-zero on the first
  failure.
- **Dogfood pilot evidence** (T-21).
  `docs/evidence/2026-05-29-dogfood-probes.md` records the literal
  B1 (30.6 s/candidate), B2 (1.0 Jaccard, 2/2 agree), and B4 (3.9
  KB/candidate) results, well above the NFR-1 and NFR-2 ceilings.
  B3 (LLM vs deterministic F1) is honestly deferred to Phase 1.5
  with prerequisites named.
- **Demo + quickstart** (T-22). `examples/quickstart.md` walks
  through a five-command audit run that does not need Ollama or
  network access (uses the bundled fixture). `docs/demo/cli/`
  holds recorded CLI outputs; `docs/demo/sample-audit/` holds a
  real audit-directory tree for layout reference.
- **Architecture and ADRs** (T-12 + T-13 + Stage 3). Nine
  Nygard-format ADRs under `docs/adr/` covering stack choice,
  registry data source, read-only static analysis, Ollama default,
  audit-db schema compatibility, verdict naming, check seed,
  popularity signal, and frontmatter parser.

### Security posture

- Runtime dependency surface is **Python standard library only**
  (`pyyaml` was considered for the check loader but the parser was
  hand-rolled instead; see ADR-009).
- Untrusted candidate source is **never executed** (ADR-003).
  `mcp-verified` performs read-only static analysis after a shallow
  `git clone --depth=1 --filter=tree:0`; no `npm install`, no
  `pip install`, no package-defined script runs against the cloned
  tree.
- Default code path **only** opens connections to
  `http://localhost:11434`, `https://registry.modelcontextprotocol.io/*`,
  and `https://github.com/*` (AC-4.4).
- Credential matches in deterministic findings are **redacted**
  before being written to the verdict registry (`sk-X...[REDACTED-N]`
  format); the verdict registry never echoes a literal token.
- Pre-commit chain runs gitleaks, ruff, a private-path leak guard,
  and a dependency-license audit on every commit; the local
  `scripts/private_path_check.sh` is the Layer 4 manual sweep.

### Known limitations

- Phase 1 audits only registry entries whose source is published on
  GitHub (~84.6% of the registry per the public-source rate observed
  in February 2026). Non-GitHub entries get the `unknown` verdict.
- Phase 1 throughput, reproducibility, and storage metrics are
  measured against a deterministic 3-entry fixture. Top-50 against
  the live registry under Ollama is a Phase 1.5 follow-up.
- CI workflows are configured but await the T-25 PUBLIC flip before
  they can run under the GitHub Free tier's billing rules.

## [0.0.1] — 2026-05-28

Initial scaffolding commit. Four-constraint baseline + dual-track
documentation contract + pre-commit chain + Python package skeleton.
