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

- **Boundary**: `mcp_verified/discovery/candidates.py` — given `list[RegistryEntry]`, score each by a documented signal and return the top-N. Score formula is pinned in a module constant (`SCORE_FORMULA_REVISION`); any change requires bumping the constant and recording it in `audit-manifest.json`.
- **Phase 1 amendment** (2026-05-29): the live registry exposes no `downloads` / `stars` / `popularity` field (probe recorded at `docs/evidence/2026-05-29-registry-no-popularity-signal-probe.md`). [ADR-008](docs/adr/ADR-008-phase1-popularity-signal.md) adopts a registry-recency-only formula `1.0 / (1.0 + days_since(updatedAt) / 30.0)` (revision `phase1-v1`); GitHub-stars enrichment is deferred to Phase 1.5.
- **Depends**: T-02.
- **AC**: AC-1.2.
- **Verify**: unit test that two runs on the same input return identical ordering; unit test that ties are broken deterministically by repository slug.
- **Effort**: S.
- **Status**: ✅ completed (30 unit tests pass, ADR-008 + evidence land).

## T-04 — Safe read-only clone

- **Boundary**: `mcp_verified/clone/safe_clone.py` — wrap `git clone --depth=1 --filter=tree:0 <url> <scratch>` with a hard prohibition on running any candidate-defined script. Returns a `ClonedRepo` with `path`, `commit_hash`, `cleanup()`. Always cleans up on exit (`with` context manager). Refuses to clone anything not on `github.com`.
- **Depends**: T-01.
- **AC**: AC-1.3, AC-1.6, AC-5.4.
- **Verify**: monkeypatched subprocess unit tests assert that only `git` is invoked (no `npm` / `pip` / `node` / `python` etc.); URL-gate negative tests cover GitLab, HTTP, missing-repo, query-string, and fragment URLs; failure / timeout tests assert the scratch directory is removed on every error path; one opt-in integration test clones `octocat/Hello-World` against the real GitHub.
- **Effort**: M.
- **Status**: ✅ completed (27 unit tests + 1 opt-in integration test pass).

## T-05 — Check loader

- **Boundary**: `mcp_verified/checks/loader.py` — load every `.md` under a checks directory, parse the frontmatter using `mcp_verified/checks/frontmatter.py`, skip files whose `status` is not `"active"`, and expose the rest as `CheckDefinition` records. Each record carries the SHA-256 of its file contents for integrity recording in `audit-manifest.json`.
- **Phase 1 amendment** (2026-05-29): the upstream `mcpserver-audit` frontmatter uses `status: active` (not `enabled: true`); the loader follows the upstream convention. [ADR-009](docs/adr/ADR-009-pyyaml-runtime-dependency.md) records the decision to ship a hand-rolled minimal subset parser (zero new runtime dependencies) rather than adopt PyYAML, in line with the harness's supply-chain security gate.
- **Depends**: T-01. (T-17 was originally listed as a dependency for fixture presence; the loader now ships its own minimal fixtures under `tests/fixtures/checks/` and does not need the seed.)
- **AC**: AC-5.5, AC-6.1.
- **Verify**: unit tests load `tests/fixtures/checks/sample-active.md` and assert id, title, status, priority, cwe, cwe-primary, tags, sections, and SHA-256; deprecated-status fixture returns None; missing-frontmatter and indented-block-list fixtures raise; curated-directory test asserts deterministic id-sorted output and that disabled entries are filtered. Plus a parser-level test set covering the supported subset (scalars, inline lists, quoted strings) and explicit rejection of unsupported shapes (block lists, inline maps, anchors, duplicate keys, indented continuations).
- **Effort**: S.
- **Status**: ✅ completed (41 unit tests pass).

## T-06 — Deterministic check executor

- **Boundary**: `mcp_verified/checks/executors/deterministic.py` — regex pattern match over the cloned tree, with a deterministic file walker (lex-sorted, skip-dir set, extension allowlist, configurable max-file-size). Returns `list[Finding]` with severity, CWE, file:line, redacted snippet. No LLM call.
- **Phase 1 amendment** (2026-05-29): Phase 1 ships regex-only; AST / semgrep-style matchers were considered and deferred. Default rule set covers seven patterns: OpenAI / Anthropic / AWS credential shapes (CWE-798), hard-coded password literal (CWE-798), `eval()` and `exec()` calls (CWE-95), and `shell=True` invocations (CWE-78). Credential matches are length-tagged and head-truncated (`[REDACTED-N]`) before being written to a finding; non-credential matches are kept intact for assessment context. The pattern set is overridable via `DeterministicExecutor(patterns=...)` so per-check markdown definitions can supply their own rules in a later task.
- **Depends**: T-04, T-05.
- **AC**: AC-1.3, AC-2.2.
- **Verify**: vulnerable fixture (`VULNERABLE_PY` with one of every default rule) asserts each rule_id appears in the result; clean fixture (`CLEAN_PY`) asserts zero findings; redaction tests assert credentials never appear in `redacted_snippet`; CWE-per-rule assertion; determinism (two runs produce identical output); walker tests cover skip-dirs (`.git/`, `node_modules/`), unrecognized extensions, oversized files, undecodable UTF-8, and missing root.
- **Effort**: M.
- **Status**: ✅ completed (17 unit tests pass).

## T-07 — Provider ABC + Ollama + mock

- **Boundary**: `mcp_verified/providers/base.py` defines the `Provider` ABC (`query(prompt, schema) -> dict`) plus the exception hierarchy (`ProviderError`, `ProviderUnreachableError`, `ProviderResponseError`) and the `query_with_fallback()` helper that swaps to mock on `ProviderUnreachableError`. `mcp_verified/providers/ollama.py` posts to `<base>/api/chat` with `format: json`, `stream: false`, configurable `model` (default `gemma3:4b` per ADR-004) and `temperature` (default 0), uses stdlib `urllib` only, and surfaces connection failures as `ProviderUnreachableError` and parse failures as `ProviderResponseError`. `mcp_verified/providers/mock.py` returns a freshly-built `{"findings": []}` object every call so downstream mutations cannot bleed into other callers.
- **Depends**: T-01.
- **AC**: AC-3.1, AC-3.2, AC-3.3.
- **Verify**: 19 unit tests covering MockProvider (empty findings, isolated copy, name, ABC membership, zero network call); OllamaProvider happy path against a stdlib `http.server` fixture (parsed content, payload pins `format: json` + `stream: false` + `temperature 0.0` + default model, custom model and temperature propagate); OllamaProvider error paths (unreachable raises `ProviderUnreachableError`, non-JSON envelope and missing `message` and non-JSON content and non-object content all raise `ProviderResponseError`); defaults sanity check; `query_with_fallback` returns primary on success, swaps to fallback on unreachable, does not swallow `ProviderResponseError`; ABC cannot be instantiated; error hierarchy verified.
- **Effort**: M.
- **Status**: ✅ completed (19 unit tests pass; cumulative 134 unit + 2 opt-in integration).

## T-08 — Paid providers (refused-by-default)

- **Boundary**: `mcp_verified/providers/{anthropic,openai,gemini}.py` extend `_PaidProviderBase` (in `_paid.py`), which provides shared HTTP plumbing and a single-line `assert_paid_opt_in(self.name)` gate at the top of every `query` call. The gate raises `PaidProviderRefusedError` unless `MCP_VERIFIED_PAID_PROVIDER_OPT_IN=1` is set; if the opt-in is granted but the vendor's key env var is missing, `PaidProviderMissingKeyError` is raised instead. Each subclass implements four hooks (`_endpoint_url`, `_headers`, `_payload`, `_extract_content`) so vendor differences (header auth vs. URL auth, message vs. choices vs. candidates response shape, max_tokens vs. response_format vs. responseMimeType structured-output knobs) are isolated to ~50 LoC per vendor.
- **Phase 1 amendment** (2026-05-29): default models pinned for Phase 1 are `claude-haiku-4-5-20251001`, `gpt-5-mini`, and `gemini-2.5-flash` — the cost-conscious tier at each vendor, so a reviewer who opts in does not accidentally burn the Opus / GPT-5 / Gemini-2.5-Pro budget on a single audit run.
- **Depends**: T-07.
- **AC**: AC-3.5, AC-4.4.
- **Verify**: 21 unit tests — `assert_paid_opt_in` gate (missing / wrong value / correct value); parametrized refused-without-opt-in tests for all three vendors with the key env var set (the gate must fire regardless); parametrized refused-with-wrong-opt-in-value tests; parametrized missing-key-when-opted-in tests; parametrized happy-path tests with `urllib.request.urlopen` monkeypatched to a fixture response, asserting the parsed content surfaces; vendor-specific request-shape tests (Anthropic carries `x-api-key` + `anthropic-version` headers and `model` + `messages` body; OpenAI carries `Authorization: Bearer` and `response_format: json_object` + `temperature: 0`; Gemini carries the key in the URL query string and `responseMimeType: application/json` in `generationConfig`); error hierarchy verification.
- **Effort**: S.
- **Status**: ✅ completed (21 unit tests pass; cumulative 155 unit + 2 opt-in integration).

## T-09 — LLM-assisted check executor

- **Boundary**: `mcp_verified/checks/executors/llm_assisted.py` — `LLMAssistedExecutor` (frozen dataclass) holds a `Provider` (default `MockProvider`), AI section title fallbacks, file-excerpt size cap, max files per prompt, and the standard skip-dirs / extension allowlist / max-file-size. `run(repo_root, checks)` filters to checks with `requires_llm: true` in `raw_frontmatter`; for each, renders a prompt that combines the `For AI Assistants: Automated Analysis` section (or a fallback section) with bounded excerpts of every candidate file, calls the provider with a JSON schema hint, coerces the response into `Finding` records, and sorts the merged output by (file, line, rule_id) so two runs against the same input produce identical output.
- **Phase 1 amendment** (2026-05-29): `ProviderResponseError` for a single check is caught and turned into one synthetic `CHECK-RUN-ERROR-<check_id>` Finding so the audit run is never aborted by one malformed LLM response. `ProviderUnreachableError` is deliberately NOT caught at this layer; callers wrap with `query_with_fallback` if they want a mock swap. Malformed individual `findings[]` entries (non-dict, type mismatches) are skipped rather than failing the whole check.
- **Depends**: T-05, T-07.
- **AC**: AC-3.2, AC-3.4.
- **Verify**: 14 unit tests covering determinism (two runs with mock produce identical output), `requires_llm` filter (eligible checks reach the provider, ineligible checks do not — and zero-eligible means zero provider calls), response parsing (well-formed findings surface; missing optional fields get defaults; non-dict entries are skipped; non-list `findings` field emits one error finding; missing `findings` field returns empty), error handling (`ProviderResponseError` becomes one error finding per failed check; `ProviderUnreachableError` propagates; missing repo root raises), and prompt construction (AI instructions surface; fallback to full body when section is missing).
- **Effort**: M.
- **Status**: ✅ completed (14 unit tests pass; cumulative 169 unit + 2 opt-in integration).

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
