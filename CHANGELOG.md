# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Portfolio quality gate (2026-05-29)

- **Fixed** — corrected the arXiv:2510.16558 author citation from
  "Wang et al." to "Li and Gao" across README, spec, ADR-002, ADR-011,
  and `checks/ATTRIBUTION.md` (verified against the arXiv abstract: the
  paper has exactly two authors, Xiaofan Li and Xing Gao).
- **Added** — `## Why this exists` narrative (motivation → approach →
  result) and a `## Demo` section with a rendered terminal screenshot
  (`docs/demo/quickstart.png`), generated from real CLI output by
  `scripts/render_demo.py` (Pillow-only, docs/dev tool).
- **Added** — `.gitattributes` forcing LF on shell scripts so the
  release gate and its tests run after a Windows clone.

### Added — design v0.2.0-design (2026-05-29, post-deep-research)

Spec / ADR / check-set upgrade grounded in the
`/deep-research` dynamic-workflow probe of 2026-05-29 (run ID
`wf_ed2457ff-557`, 113 subagents, 5,428,885 output tokens, full
results persisted under
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`).

- **Spec § F-008** — MCP-specific threat-surface coverage. Eight new
  acceptance criteria (AC-8.1 through AC-8.8) codify the design-level
  requirements for flag-injection bypass detection, supply-chain
  pre-install hook detection, maintainer-graph blast-radius
  inspection, token-lifecycle policy inspection, rug-pull static
  precondition + dynamic-probe split, orchestrator sandbox doctrine,
  MCP debug log redaction, and per-check MCP-protocol category
  declarations.
- **ADR-010** — Sandbox doctrine for any future stdio-probe stage.
  Six binding constraints (disposable sandbox, flag-level allowlist,
  explicit `--dangerously-execute` opt-in, per-probe budgets,
  network-egress deny-by-default, result laundering) that any future
  PR adding a dynamic stage must satisfy.
- **ADR-011** — MCP-protocol threat taxonomy adoption stance.
  `mcpserver-audit` six-category + `mcp-scan` matrix adopted as design
  inspiration only; coverage claims constrained to per-check
  declarations. Adds a controlled vocabulary of category slugs and
  forbids over-claiming "covers" language in marketing copy.
- **ADR-012** — Schema-hash diff as the canonical detection signal for
  the rug-pull tool-mutation class. Phase 1 ships the
  static-precondition fallback; full dynamic schema-hash diff reserved
  for the future probe stage governed by ADR-010.
- **Check** — `command-injection-flag-bypass-check.md`. Grep patterns
  for direct command/subprocess injection sinks plus the flag-injection
  bypass class against command allowlists. Cites Upsonic
  CVE-2026-30625, Flowise CVE-2026-40933, `mcp-remote` CVE-2025-6514,
  `figma-developer-mcp` CVE-2025-53967, `gemini-mcp-tool` CVE-2026-0755.
- **Check** — `supply-chain-preinstall-hook-check.md`. npm lifecycle
  hook inspection prompted by Shai-Hulud's November 2025 pivot from
  `postinstall` to `preinstall` execution (Unit42).
- **Check** — `supply-chain-maintainer-blast-radius-check.md`.
  Maintainer-graph sibling-package enumeration as a combined-signal
  input. Tiered severity (1 / 2–9 / 10–49 / 50+ sibling packages).
- **Check** — `token-lifecycle-policy-check.md`. OWASP MCP Top 10
  (2025) MCP01 detection criteria for TTL > session duration and
  absence of enforced rotation.
- **Check** — `tool-schema-mutation-rug-pull-check.md`. Static
  precondition for rug-pull — flags tool-definition construction
  sites whose `name` / `description` / `inputSchema` / `annotations`
  derive from runtime-mutable state.
- **Check** — `mcp-debug-log-redaction-check.md`. Orthogonal to the
  upstream-forked credential-storage check; targets the OWASP MCP01
  Scenario 2 "Log Scraping" failure mode.
- **README — Limitations and honest framing**. Three new bullets
  cover the taxonomy non-claim (ADR-011), the rug-pull static / dynamic
  split (ADR-010 + ADR-012), and the Equixly prevalence figures that
  did not survive adversarial verification (intent: position the
  Phase 1.5 pilot as the first credible numerator/denominator
  measurement on the official registry).
- **`checks/ATTRIBUTION.md`** — six new entries in the "added in this
  fork" section, each linked to the evidence file section that
  motivated it.
- **`docs/adr/INDEX.md`** — three new ADR rows.
- **`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`** —
  full persistence of the dynamic-workflow run (metadata, decomposition,
  seven confirmed findings, seven refuted claims, four open questions
  for Phase 1.5, 30 sources with quality tags).

### Design impact

No source-code changes in this batch. The implementation of the new
checks against the verdict aggregator is a Phase 1.5 deliverable. The
intent of this design-only release is to lock in the threat-surface
coverage and honest-framing constraints **before** the next code change
so future PRs cannot quietly weaken them.

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
