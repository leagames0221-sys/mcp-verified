# mcp-verified — Specification (Phase 1)

> Authoritative specification for Phase 1 of `mcp-verified`. Acceptance criteria are written in EARS (Easy Approach to Requirements Syntax) format. Phase 2 covers the demo video build; Phase 3 covers public-release verification and the visibility flip from private to public.

## 1. Scope

Phase 1 delivers a command-line tool that:

1. Discovers MCP server entries published in the official MCP registry.
2. For each discovered entry whose source repository is public on GitHub, performs read-only static analysis using a modular set of security checks.
3. Emits per-server findings and a tier verdict (`verified` / `caution` / `risky` / `unknown`) into a directory structure schema-compatible with the Cloud Security Alliance `audit-db` project.
4. Uses a local LLM (Ollama, `gemma3:4b` by default) for any AI-assisted deep review; never makes a paid-API call in the default code path.

Phase 1 scope excludes: live network probing of MCP servers, runtime exploit verification, contribution upstreaming to `audit-db` (deferred to Phase 1.5), the demo video (Phase 2), the public-release flip (Phase 3).

## 2. Functional features

- **F-001 — Registry-wide batched audit pipeline** (KF-1): discover → safe clone → check run → aggregate verdict.
- **F-002 — Queryable verdict registry** (KF-2): on-disk directory schema compatible with `audit-db`.
- **F-003 — Reproducible local-LLM deep review** (KF-3): identical Ollama configuration produces identical verdicts within an agreed tolerance.
- **F-004 — Four-constraint posture** (cross-cutting): free, no credit card, local-first, security-first.
- **F-005 — CSA audit-db schema compatibility** (cross-cutting).

## 3. Acceptance criteria (EARS)

### F-001 — Registry-wide batched audit pipeline (KF-1)

- **AC-1.1 (Ubiquitous)** — The CLI shall provide a subcommand `mcp-verified audit` that accepts `--top N` to limit the audit to the N most-popular servers and `--out <dir>` to set the output directory.
- **AC-1.2 (Event-driven)** — When `mcp-verified audit` is invoked, the system shall read the registry inventory, select the top-N candidates by a documented popularity signal, and process each candidate exactly once per invocation.
- **AC-1.3 (Event-driven)** — When a candidate's source repository URL is `https://github.com/...` and is publicly accessible, the system shall perform a shallow read-only clone (`git clone --depth=1 --filter=tree:0`) into a per-run scratch directory, run the configured check set against the cloned tree, and remove the clone before exiting.
- **AC-1.4 (Event-driven)** — When a candidate's source is unreachable or not on GitHub, the system shall record a `findings_summary` of `{ unknown: 1 }` and a verdict of `unknown`, without attempting further analysis.
- **AC-1.5 (State-driven)** — While processing a candidate, the system shall enforce a 5-minute per-server wall-clock budget; if exceeded, the system shall abort that candidate, record a `timeout` finding, and proceed to the next.
- **AC-1.6 (Unwanted behavior)** — If any check attempts to invoke a candidate's `package.json`, `setup.py`, or other installer-defined script, the audit run shall abort with a non-zero exit code and a clear error message indicating that running untrusted code is forbidden in Phase 1.
- **AC-1.7 (Ubiquitous)** — The CLI shall print, at end-of-run, a one-line summary of `{audited, verified, caution, risky, unknown, timeout, error}` counts to stdout.

### F-002 — Queryable verdict registry (KF-2)

- **AC-2.1 (Ubiquitous)** — Per-server output shall be written under `<out>/audits/<host>/<owner>/<repo>/audits/<auditor>-<YYYY-MM-DD>-<NNN>/`, with `<host>` = `github.com`, `<auditor>` = a configured short identifier, and `<NNN>` = a three-digit zero-padded run sequence within that auditor-date pair.
- **AC-2.2 (Ubiquitous)** — Each per-server output directory shall contain `security-assessment.md` (top-level summary), a `findings/` subdirectory with one markdown file per finding named `<severity>-<NNN>-<slug>.md`, and `audit-manifest.json`.
- **AC-2.3 (Ubiquitous)** — `audit-manifest.json` shall contain the fields `audit_id`, `auditor` (with sub-fields `name`, `github`, `org`), `target` (with sub-fields `repo_url`, `commit_hash`, `version`), `audit_metadata` (with sub-fields `started_at`, `finished_at`, `status`, `time_spent_minutes`), `findings_summary` (severity counts), `tools_used` (list of strings), and `compliance_checks` (list of strings).
- **AC-2.4 (Ubiquitous)** — A `<out>/audits/<host>/<owner>/<repo>/metadata.json` aggregate shall list the latest verdict, the latest audit directory pointer, and the cumulative count of audits performed against that target.
- **AC-2.5 (Event-driven)** — When two runs against the same `(target.repo_url, target.commit_hash)` produce divergent verdicts, the system shall log a `verdict_divergence` warning and write a `discrepancy.md` alongside the second run's `security-assessment.md`.

### F-003 — Reproducible local-LLM deep review (KF-3)

- **AC-3.1 (Ubiquitous)** — The default LLM provider shall be Ollama at `http://localhost:11434` using the model name pinned in `pyproject.toml` (`gemma3:4b` for Phase 1).
- **AC-3.2 (Event-driven)** — When a check requires LLM-assisted analysis, the system shall call the configured provider with `temperature=0`, a pinned system prompt revision, and a structured-output schema; the response shall be parsed as JSON or rejected.
- **AC-3.3 (State-driven)** — While the configured provider is unreachable, the system shall fall back to a deterministic mock that emits the empty-finding structured output, and shall annotate `tools_used` with `mock-provider` so downstream consumers can filter mock-derived verdicts.
- **AC-3.4 (Ubiquitous)** — For a fixed `(model, system prompt revision, input)`, two consecutive Ollama-backed runs shall produce findings whose set-Jaccard similarity is ≥ 0.90 and whose top-level verdict agrees, across a documented N=5 reproducibility sample.
- **AC-3.5 (Unwanted behavior)** — If the user has not set an environment variable explicitly enabling a paid provider (`MCP_VERIFIED_PAID_PROVIDER_OPT_IN=1`), then the system shall refuse to use Anthropic, OpenAI, or Gemini providers even when their API keys are present in the environment.

### F-004 — Four-constraint posture (cross-cutting)

- **AC-4.1 (Ubiquitous)** — The default code path shall complete an audit run of at least one fixture server using only free, locally-installed software (Python ≥ 3.11, Ollama, `git`), with no account creation and no credit card on file.
- **AC-4.2 (Ubiquitous)** — Every runtime dependency declared in `pyproject.toml` shall carry a permissive OSS license (MIT, Apache 2.0, BSD-2-Clause, BSD-3-Clause, or ISC) as enforced by `scripts/audit_deps.py`.
- **AC-4.3 (Ubiquitous)** — Every new runtime dependency introduced after the v0.0.1 baseline shall be justified in an architecture decision record under `docs/adr/` before being merged to `main`.
- **AC-4.4 (Ubiquitous)** — The default code path shall never open a network connection to anything other than `http://localhost:*`, `https://github.com/*`, `https://api.github.com/*`, and `https://registry.modelcontextprotocol.io/*`. Any additional outbound endpoint shall be documented and gated behind an explicit opt-in flag.

### F-005 — Security hardening

- **AC-5.1 (Ubiquitous)** — Pre-commit hooks shall run gitleaks, ruff, the private-path leak guard, and the dependency license audit on every `git commit`.
- **AC-5.2 (Event-driven)** — When the private-path leak guard finds any tracked file containing an absolute Windows user path, an internal local-config directory reference, or a documented internal-name abstraction, the commit shall be blocked with exit code 1.
- **AC-5.3 (Event-driven)** — When `gh repo edit --visibility public` is requested (Phase 3), a release-gate script shall verify that no commit in the full history of `main` contains any item from the customer-name and internal-name word lists, both in tracked file content and in commit messages.
- **AC-5.4 (Unwanted behavior)** — If a candidate's cloned source contains a `package-lock.json`, `Pipfile.lock`, or other lockfile, the system shall parse it for known-compromised package identifiers, but shall not invoke the package manager to install anything.
- **AC-5.5 (Ubiquitous)** — Every audit shall record the SHA-256 of the cloned tree's git commit and the SHA-256 of each check definition file used; both shall appear in `audit-manifest.json` under `audit_metadata.integrity`.

### F-006 — CSA audit-db schema compatibility

- **AC-6.1 (Ubiquitous)** — `audit-manifest.json` shall validate against the schema documented in the upstream `audit-db` repository as of the dependency pin recorded in `docs/adr/`.
- **AC-6.2 (Event-driven)** — When the upstream schema version changes, the system shall surface the diff in CI as a warning and require an ADR to update the pin.
- **AC-6.3 (Ubiquitous)** — A `mcp-verified export-audit-db <repo>` subcommand shall emit a tarball laid out exactly as expected by an `audit-db` pull request, suitable for direct submission upstream.

### F-007 — Phase 3 public-release gate

- **AC-7.1 (Ubiquitous)** — Before requesting visibility change to public, the release gate shall verify:
  - All Phase 1 unit and integration tests pass on the current `main`.
  - The 4-constraint default code path completes against at least one fixture server end-to-end.
  - The customer-name word list shows zero hits across all tracked files, commit history, and GitHub server-side refs (`refs/heads/*`, `refs/tags/*`, `refs/pull/*`).
  - The internal-name word list shows zero hits across the same surfaces.
  - At least five Nygard-format ADRs exist under `docs/adr/`, each with the four canonical sections.
  - A `LIMITATIONS` section is present in `README.md` documenting at least three honest limitations.
  - The `SECURITY.md` reporting channel resolves to an active GitHub Security Advisory inbox on this repository.
- **AC-7.2 (Unwanted behavior)** — If any item in AC-7.1 fails, the release gate shall print the failing item, exit non-zero, and refuse to invoke `gh repo edit --visibility public`.
- **AC-7.3 (Event-driven)** — When the release gate passes, the operator shall manually inspect the verdict registry's first ten entries before invoking the visibility change, and shall record the inspection result in `docs/evidence/public-release-readiness-<date>.md`.

## 4. Non-functional requirements

- **NFR-1 — Throughput**: a top-50 audit run shall complete within one weekend (~16 wall-clock hours) on a consumer laptop with 16 GB RAM (8 GB available for Ollama). To be validated as Phase 1.5 probe B1.
- **NFR-2 — Storage scale**: per-server output (markdown + JSON) shall fit within 100 KB on average; total top-50 output shall fit within 10 MB. To be validated as probe B4.
- **NFR-3 — Onboarding**: a reviewer following only `README.md` Quickstart shall reach a green audit run in ≤ 10 commands and ≤ 30 minutes (excluding model download).
- **NFR-4 — Cross-platform**: Phase 1 supports Windows 11 (primary) and Linux (CI). macOS support is best-effort; failing macOS tests do not block release.
- **NFR-5 — Honest framing**: the README shall not use the words "industry first", "best in class", "production ready", or "enterprise grade" without a primary-source citation that supports the claim.

## 5. Out of scope (Phase 1)

- Continuous re-audit on registry changes (deferred to Phase 4 or downstream).
- Web UI for browsing verdicts (Phase 1 is CLI + filesystem registry only).
- Per-finding remediation patches (the `mcp-guard` companion covers configuration-level remediation; source-level patch suggestion is deferred).
- Cross-registry coverage (`mcp.so`, Smithery, MCP Market) — Phase 1 is official-registry only.
- Threat-model coverage of indirect prompt injection at the MCP-protocol layer (covered by `mcp-guard`).

## 6. References

- `README.md` — public-facing project description.
- `SECURITY.md` — hardening posture, reporting channel.
- `docs/adr/` — architecture decision records.
- Upstream: [`mcpserver-audit`](https://github.com/ModelContextProtocol-Security/mcpserver-audit), [`audit-db`](https://github.com/ModelContextProtocol-Security/audit-db).
- Threat model source: Wang et al., "A First Look at the Security Issues in the Model Context Protocol Ecosystem" (arXiv:2510.16558).
