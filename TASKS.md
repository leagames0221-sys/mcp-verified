# Tasks — Phase 1 implementation

> Each task names: its **Boundary** (what it adds / does not add), its **Depends** (predecessor task IDs), the **acceptance criteria** from `spec.md` it satisfies (AC-x.y), and a literal **Verify** step. Tasks are executed top-down; a task is not closed until its Verify step passes.
>
> Effort hints: S ≈ ½ day, M ≈ 1 day, L ≈ 2–3 days on a consumer laptop with Ollama running.

## Constraint envelope (cross-cutting, applies to every task)

- **Free** — every dependency declared must clear `scripts/audit_deps.py`. No paid services in the default code path.
- **No credit card** — no account creation, no paid-API call in any test, any CI step, or any default code path.
- **Local-first** — default code path talks only to `http://localhost:11434`, `https://github.com/*`, `https://registry.modelcontextprotocol.io/*` (AC-4.4).
- **Security-first** — every task ends with a Layer 4 sweep before commit; every commit triggers pre-commit (gitleaks + ruff + private-path guard + license audit).

---

## T-01 — Scaffolding baseline

- **Status**: ✅ completed (commit `e807fe0`).
- **Boundary**: 11-file skeleton, dual-track `.gitignore`, MIT license, pre-commit chain wired.
- **Depends**: (none).
- **AC**: AC-4.2, AC-5.1, AC-5.2.
- **Verify**: `bash scripts/private_path_check.sh` exit 0; `pre-commit run --all-files` passes locally; `git push` succeeds.

## T-02 — Registry client

- **Boundary**: `mcp_verified/registry/client.py` — fetch the inventory from `registry.modelcontextprotocol.io`, parse the documented JSON shape, return a `list[RegistryEntry]`. Cache to `~/.cache/mcp-verified/registry-<sha>.json` with a documented TTL. No popularity scoring here.
- **Depends**: T-01.
- **AC**: AC-1.2, AC-4.4.
- **Verify**: unit test against a recorded JSON fixture (`tests/fixtures/registry-snapshot.json`); integration test (skipped unless network present) that fetches and asserts ≥ 1 entry with the documented field set.
- **Effort**: S.

## T-03 — Discovery / popularity scoring

- **Boundary**: `mcp_verified/discovery/candidates.py` — given `list[RegistryEntry]`, score each by a documented signal (default: GitHub stars × log10(downloads) with a freshness penalty) and return the top-N. Score formula is pinned in a docstring; any change requires bumping a docstring revision and recording it in `audit-manifest.json`.
- **Depends**: T-02.
- **AC**: AC-1.2.
- **Verify**: unit test that two runs on the same input return identical ordering; unit test that ties are broken deterministically by repository slug.
- **Effort**: S.

## T-04 — Safe read-only clone

- **Boundary**: `mcp_verified/clone/safe_clone.py` — wrap `git clone --depth=1 --filter=tree:0 <url> <scratch>` with a hard prohibition on running any candidate-defined script. Returns a `ClonedRepo` with `path`, `commit_hash`, `cleanup()`. Always cleans up on exit (`with` context manager). Refuses to clone anything not on `github.com`.
- **Depends**: T-01.
- **AC**: AC-1.3, AC-1.6, AC-5.4.
- **Verify**: unit test against a recorded git bundle (`tests/fixtures/sample-repo.bundle`); negative test that asserts a non-`github.com` URL raises; negative test that asserts no subprocess call invokes `npm`, `pip`, `node`, `python` against cloned content.
- **Effort**: M.

## T-05 — Check loader

- **Boundary**: `mcp_verified/checks/loader.py` — load every `.md` under `checks/` whose frontmatter declares `enabled: true`, parse the five-section structure (CWE tag, AI instructions, human steps, risk, good/bad examples), expose them as `list[CheckDefinition]`. Compute a SHA-256 per file for integrity recording.
- **Depends**: T-01, T-17 (seed file presence).
- **AC**: AC-5.5, AC-6.1.
- **Verify**: unit test that loads `tests/fixtures/checks/*.md` and asserts the expected per-file SHA-256.
- **Effort**: S.

## T-06 — Deterministic check executor

- **Boundary**: `mcp_verified/checks/executors/deterministic.py` — regex / AST / semgrep-style pattern match against the cloned tree. Returns `list[Finding]` with severity, CWE, file:line, snippet. No LLM call.
- **Depends**: T-04, T-05.
- **AC**: AC-1.3, AC-2.2.
- **Verify**: unit test against a "vulnerable fixture" tree that triggers each rule at least once; unit test against a "clean fixture" tree that produces zero findings.
- **Effort**: M.

## T-07 — Provider ABC + Ollama + mock

- **Boundary**: `mcp_verified/providers/base.py` defines the ABC `query(prompt: str, schema: dict) -> dict`. `mcp_verified/providers/ollama.py` posts to `http://localhost:11434/api/chat` with `temperature=0`, parses the response as JSON, validates against `schema`. `mcp_verified/providers/mock.py` returns an empty-finding object that validates against `schema`. Mock is the active provider when the configured provider is unreachable (catch `ConnectionError`).
- **Depends**: T-01.
- **AC**: AC-3.1, AC-3.2, AC-3.3.
- **Verify**: unit test of `ollama.query` against a recorded HTTP fixture (`responses` library or stdlib `http.server`); unit test that mock provider returns the documented empty-finding object; unit test that an unreachable provider triggers mock fallback.
- **Effort**: M.

## T-08 — Paid providers (refused-by-default)

- **Boundary**: `mcp_verified/providers/{anthropic,openai,gemini}.py` — same ABC as Ollama, but `query` checks `os.environ["MCP_VERIFIED_PAID_PROVIDER_OPT_IN"]`; if not equal to `"1"`, raise `PaidProviderRefusedError` regardless of whether the vendor's API key is present.
- **Depends**: T-07.
- **AC**: AC-3.5, AC-4.4.
- **Verify**: unit test that each paid provider refuses without the opt-in env var even when the key env var is set; unit test that with both env vars set, the provider proceeds (mock the HTTP layer).
- **Effort**: S.

## T-09 — LLM-assisted check executor

- **Boundary**: `mcp_verified/checks/executors/llm_assisted.py` — for checks whose frontmatter declares `requires_llm: true`, render the `AI instructions` section + selected file excerpts as the prompt, call the configured provider with a per-check JSON schema, parse the response, emit `list[Finding]`.
- **Depends**: T-05, T-07.
- **AC**: AC-3.2, AC-3.4.
- **Verify**: unit test that two consecutive runs against the mock provider produce identical findings; unit test that a malformed (non-JSON) response is rejected and the check returns `error` not a partial result.
- **Effort**: M.

## T-10 — Per-server budget enforcer

- **Boundary**: `mcp_verified/budget/per_server.py` — wrap an audit run in a `signal.alarm(300)` (Linux) / `concurrent.futures.TimeoutError` (Windows) with cleanup on timeout. On timeout, emit a `timeout` finding and continue with the next candidate.
- **Depends**: T-04.
- **AC**: AC-1.5.
- **Verify**: unit test that a deliberately slow check (`time.sleep(310)` mock) aborts at 300 s ± 5 s; unit test that the timeout finding is recorded with the right severity.
- **Effort**: S.

## T-11 — Verdict aggregator

- **Boundary**: `mcp_verified/verdict/aggregator.py` — `list[Finding]` → `verdict ∈ {verified, caution, risky, unknown}` per the rule "any high → risky; any medium, no high → caution; all clean → verified; no audit completed → unknown".
- **Depends**: (none of the executors; pure function on `Finding` objects).
- **AC**: F-002 verdict semantics; AC-2.2.
- **Verify**: unit test covering all four verdict branches with hand-built `Finding` lists.
- **Effort**: S.

## T-12 — Divergence detector

- **Boundary**: `mcp_verified/verdict/divergence.py` — read prior `audit-manifest.json` for the same `(target.repo_url, target.commit_hash)`; if the prior verdict differs from the current one, write `discrepancy.md` alongside the new `security-assessment.md`.
- **Depends**: T-11, T-13.
- **AC**: AC-2.5.
- **Verify**: unit test against a fixture with a fake prior run that has a different verdict; asserts `discrepancy.md` is written with the documented field set.
- **Effort**: S.

## T-13 — Output writer (manifest + assessment + findings)

- **Boundary**: `mcp_verified/output/{manifest,assessment,findings}.py` — write the per-server directory tree per AC-2.1, AC-2.2, AC-2.3, AC-2.4 with the exact `audit-db` schema.
- **Depends**: T-11.
- **AC**: AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-5.5, AC-6.1.
- **Verify**: integration test that writes a fixture verdict and validates the resulting JSON against the upstream `audit-db` schema (pinned commit hash in ADR-005); shape-test of `findings/<severity>-<NNN>-<slug>.md` naming.
- **Effort**: M.

## T-14 — `export-audit-db` subcommand

- **Boundary**: `mcp_verified/output/exporter.py` — given a target repo's audit directory, emit a tarball laid out exactly as an `audit-db` PR expects.
- **Depends**: T-13.
- **AC**: AC-6.3.
- **Verify**: integration test that runs `mcp-verified export-audit-db <fixture-target>`, extracts the tarball, and asserts the directory tree matches an upstream-schema-validated reference layout.
- **Effort**: S.

## T-15 — CLI entry point

- **Boundary**: `mcp_verified/cli.py` — `argparse` with subcommands `audit`, `export-audit-db`, `version`. `audit` accepts `--top N`, `--out <dir>`, `--checks <dir>`, `--provider <name>`. End-of-run prints one-line summary `{audited, verified, caution, risky, unknown, timeout, error}` to stdout (AC-1.7).
- **Depends**: T-02, T-03, T-04, T-06, T-09, T-10, T-11, T-13, T-14.
- **AC**: AC-1.1, AC-1.7.
- **Verify**: e2e smoke `mcp-verified audit --top 1 --provider mock --out /tmp/smoke` produces a non-empty audit directory and the summary line on stdout.
- **Effort**: M.

## T-16 — Integrity hashing

- **Boundary**: `mcp_verified/integrity/hash.py` — SHA-256 of cloned tree commit, SHA-256 of each check file used. Emitted under `audit-manifest.json` `audit_metadata.integrity`.
- **Depends**: T-04, T-05, T-13.
- **AC**: AC-5.5.
- **Verify**: unit test that hashes are deterministic across two runs against the same fixture.
- **Effort**: S.

## T-17 — Check seed: fork mcpserver-audit

- **Boundary**: copy upstream `checks/*.md` into this repo's `checks/`, preserving the five-section structure and CWE-tag frontmatter. Land `checks/ATTRIBUTION.md` recording upstream commit hash, Apache 2.0 license terms, and date of fork. Three MCP-specific extensions (`mcp-transport-security.md`, `tool-poisoning-detection.md`, `redirect-hijacking.md`) modeled on arXiv 2510.16558 attack taxonomy.
- **Depends**: T-01.
- **AC**: AC-6.1.
- **Verify**: `bash scripts/private_path_check.sh` clean; `pre-commit run --all-files` clean; `checks/ATTRIBUTION.md` validated by hand against upstream commit hash.
- **Effort**: M.

## T-18 — Tests + coverage

- **Boundary**: per-task unit tests live alongside each module under `tests/`; integration tests under `tests/integration/`. Coverage gate ≥ 80% line on `mcp_verified/`.
- **Depends**: all preceding implementation tasks.
- **AC**: F-001 through F-006 unit-test surfaces.
- **Verify**: `pytest -q` exit 0; `pytest --cov=mcp_verified --cov-fail-under=80` exit 0.
- **Effort**: L.

## T-19 — GitHub Actions workflows

- **Boundary**: `.github/workflows/ci.yml` (test + lint on push / PR to `main`); `.github/workflows/gitleaks.yml` (secrets scan on push / PR); `.github/workflows/secrets-scan.yml` (redundant post-push scan). Cross-OS matrix (ubuntu-latest, windows-latest); macOS best-effort, allowed to fail per NFR-4.
- **Depends**: T-18.
- **AC**: AC-5.1, NFR-4.
- **Verify**: workflows green on the first push to `main` after landing; `gh run list --limit 5` shows the expected job names.
- **Effort**: M.

## T-20 — Release gate script

- **Boundary**: `scripts/release_gate.sh` — run the F-007 / AC-7.1 checklist (tests pass, 4-constraint end-to-end run completes, customer + internal word-list sweeps clean across tracked files + full commit history + GitHub server-side refs `refs/heads/*` + `refs/tags/*` + `refs/pull/*`, ≥ 5 ADRs land, LIMITATIONS section in README, SECURITY.md reporting channel resolves).
- **Depends**: T-19.
- **AC**: AC-7.1, AC-7.2.
- **Verify**: deliberate negative test against a synthetic commit containing a fake customer-name string; asserts the gate exits non-zero with the specific failing item logged.
- **Effort**: M.

## T-21 — Dogfood probes B1–B4 baseline

- **Boundary**: run a top-50 audit, measure: B1 throughput (wall-clock / server), B2 reproducibility (Jaccard across 2 runs on N=5 servers), B3 LLM vs deterministic F1 against a ground-truth N=10 set, B4 storage scale (KB / server). Record results under `docs/evidence/<date>-dogfood-probes.md`.
- **Depends**: T-15, T-17, T-18, T-19.
- **AC**: NFR-1, NFR-2.
- **Verify**: evidence file lands with concrete numbers in every probe row; `git log` shows the file was added in a single commit with the dogfood run output.
- **Effort**: L (wall-clock-dominated, not effort-dominated).

## T-22 — README screenshots + examples

- **Boundary**: `docs/demo/` — capture CLI output via `asciinema rec` → PNG via documented render path, embed in README. Add an `examples/quickstart.md` that walks through `mcp-verified audit --top 5`.
- **Depends**: T-15, T-21.
- **AC**: NFR-3.
- **Verify**: README renders correctly on GitHub PRIVATE; example commands copy-paste-runnable.
- **Effort**: S.

## T-23 — v0.1.0 tag

- **Boundary**: bump `pyproject.toml` and `mcp_verified/__init__.py` to `0.1.0`; update CHANGELOG.md; create annotated tag `v0.1.0`; push tag.
- **Depends**: T-19, T-20, T-21, T-22.
- **AC**: (release milestone).
- **Verify**: `gh release view v0.1.0` returns the expected metadata; `git tag` lists `v0.1.0`.
- **Effort**: S.

---

## Phase 3 tasks (PUBLIC release flip)

> Executed only after Phase 1.5 dogfood probes (T-21) confirm the four constraints hold under empirical load and the Phase 3 release-gate checklist (F-007) passes.

## T-24 — Release gate execution

- **Boundary**: run `scripts/release_gate.sh` against the current `main`; address any failing items; produce `docs/evidence/<date>-public-release-readiness.md` recording the pass output.
- **Depends**: T-20, T-21, T-22, T-23.
- **AC**: AC-7.1, AC-7.2.
- **Verify**: gate script exit 0; evidence file present with the full pass output captured.
- **Effort**: S–M (depends on how many items need addressing).

## T-25 — Visibility flip + post-flip verify

- **Boundary**: `gh repo edit leagames0221-sys/mcp-verified --visibility public`; immediately run a post-flip sweep verifying the customer-name and internal-name word lists are still clean against `refs/heads/*`, `refs/tags/*`, `refs/pull/*` (GitHub server-side state); record the result under `docs/evidence/<date>-public-flip-complete.md`.
- **Depends**: T-24.
- **AC**: AC-7.3.
- **Verify**: `gh repo view --json visibility` returns `"PUBLIC"`; post-flip sweep clean; CI runs green on the next push under PUBLIC tier (= free GitHub Actions minutes for PUBLIC repos per the upstream billing policy).
- **Effort**: S.

---

## Task graph (summary)

```
T-01 ─┬─ T-02 ─ T-03 ──────────────────────────────────────┐
      ├─ T-04 ─ T-06 ────────────────────────────────────┐ │
      ├─ T-05 ─┤                                         │ │
      ├─ T-07 ─ T-08                                     │ │
      │        └─ T-09 ─────────────────────────────────┐│ │
      ├─ T-17 ─┘                                        ││ │
      └─ T-10 ────────────────────────────────────────┐ ││ │
                       T-11 ─ T-12 ─ T-13 ─ T-14      │ ││ │
                                  └─ T-16             │ ││ │
                                                      └─┴┴─┴─ T-15 ─ T-18 ─ T-19 ─ T-20
                                                                                  └─ T-21 ─ T-22 ─ T-23 ─ T-24 ─ T-25
```

Parallelizable: {T-02, T-04, T-05, T-07, T-10, T-17} after T-01; T-06 after {T-04, T-05}; T-08, T-09 after T-07; T-15 once all executors land. Linear from T-18 onward.
