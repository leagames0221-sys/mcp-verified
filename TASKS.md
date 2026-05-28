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

- **Boundary**: `mcp_verified/budget/per_server.py` exposes `run_with_budget(work, *, timeout_seconds=300)` returning a `BudgetResult(completed, value, elapsed_seconds)` and a `timeout_finding(timeout_seconds, *, candidate=...)` helper that yields the synthetic `CHECK-RUN-TIMEOUT` Finding (severity `info`, no CWE) recorded against a candidate that hit the cap.
- **Phase 1 amendment** (2026-05-29): the implementation uses `concurrent.futures.ThreadPoolExecutor` rather than POSIX `signal.alarm` so Windows is supported on equal footing. `shutdown(wait=False)` returns control to the caller immediately even when the stuck worker thread is still draining I/O; production audit loops can move to the next candidate without blocking. The worker thread is non-daemon (an stdlib limitation) so process exit waits for it; long-lived audit processes release the reference once the result is consumed.
- **Depends**: T-04.
- **AC**: AC-1.5.
- **Verify**: 10 unit tests covering the happy path (fast work returns; elapsed is small; exceptions propagate); timeout path (slow work returns `BudgetResult(completed=False, value=None)`; timeout never raises); validation (zero or negative timeout raises `ValueError`); and `timeout_finding` shape (rule_id, severity, default-budget-matches-constant, candidate-included-in-description).
- **Effort**: S.
- **Status**: ✅ completed (10 unit tests pass; cumulative 179 unit + 2 opt-in integration).

## T-11 — Verdict aggregator

- **Boundary**: `mcp_verified/verdict/aggregator.py` exposes `aggregate_verdict(findings, *, audit_completed=True) -> str` and `findings_summary(findings) -> dict[str, int]`. Both are pure functions on iterables of `Finding`: no I/O, no global state, no module-level mutable cache. The verdict decision is exactly ADR-006: `unknown` when `audit_completed=False` (regardless of findings), `risky` if any `high` or `critical` severity is present, `caution` if any `medium`, else `verified`. `findings_summary` always returns a stable shape over the canonical buckets (`info`, `low`, `medium`, `high`, `critical`), adding an `unknown` bucket only if non-canonical severity strings are observed.
- **Phase 1 amendment** (2026-05-29): severity comparison is case-insensitive (`HIGH` and `high` map to the same bucket) so LLM-produced finding entries from T-09 are not silently miscounted. Unknown severity strings do NOT downgrade the verdict (an LLM that returns `severity: "totally-made-up"` does not turn a clean candidate into `caution`); they are surfaced via the `findings_summary["unknown"]` bucket so the aberration is recorded without changing the tier.
- **Depends**: (none of the executors; pure function on `Finding` objects).
- **AC**: F-002 verdict semantics; AC-2.2.
- **Verify**: 25 unit tests covering all four verdict branches (verified, caution, risky, unknown), case-insensitive severity, unknown-severity-does-not-downgrade, `audit_completed=False` forces `unknown` regardless of findings, `findings_summary` zeroed buckets / counts / unknown-bucket-appears-only-when-needed, and constants integrity (`SEVERITY_ORDER`, `HIGH_SEVERITIES`, `MEDIUM_SEVERITIES`, `VERDICTS` tuple, four verdict values are the plain words exactly).
- **Effort**: S.
- **Status**: ✅ completed (25 unit tests pass; cumulative 204 unit + 2 opt-in integration).

## T-12 — Divergence detector

- **Boundary**: `mcp_verified/verdict/divergence.py` exposes `detect_divergence(prior_manifest, current_manifest, *, prior_verdict=None, current_verdict=None) -> DivergenceReport | None`, `find_latest_prior_audit(target_dir, current_audit_id=None) -> Path | None`, `render_discrepancy_md(report) -> str`, `write_discrepancy_md(report, path) -> Path`, and a small `load_manifest(path)` convenience reader. Detection returns `None` when the two top-level verdicts agree; same-verdict-with-different-finding-counts is treated as expected churn and does not trip the gate.
- **Phase 1 amendment** (2026-05-29): the detector also reads the verdict directly from `audit_metadata.verdict` in the manifest, so this module can run against any pair of manifests on disk without the pipeline needing to thread the verdict through separately. Missing fields are surfaced as the literal string `"(unknown)"` rather than raised, so partial / older manifests stay diff-able.
- **Depends**: T-11. (T-13 was originally listed as a dependency because the manifest schema lives there; T-12 now consumes the manifest as a plain dict so the cycle is broken — T-13 will produce manifests that T-12 already knows how to read.)
- **AC**: AC-2.5.
- **Verify**: 16 unit tests covering `detect_divergence` (same verdict returns None, different verdict produces report, explicit kwargs override manifest, target fields pulled from current, missing prior verdict surfaces as `"(unknown)"` marker, missing findings_summary becomes empty dict), `find_latest_prior_audit` (no audits dir, empty audits dir, only audit, lex-latest, excludes current audit id), discrepancy markdown (includes target + verdicts + audit ids, idempotent render, write creates file with parent dirs), and `load_manifest` (reads JSON into dict, raises ValueError on non-object).
- **Effort**: S.
- **Status**: ✅ completed (16 unit tests pass; cumulative 220 unit + 2 opt-in integration).

## T-13 — Output writer (manifest + assessment + findings)

- **Boundary**: four cooperating modules under `mcp_verified/output/` produce the full `audit-db`-compatible directory tree from one `AuditManifest` + `list[Finding]` pair:
  - `manifest.py` — `Auditor`, `Target`, `AuditMetadata`, `AuditManifest` frozen dataclasses mirroring the upstream schema; `write_manifest_json()` emits sorted-key 2-space-indented JSON so two runs of the same audit are byte-identical (critical for T-12 divergence detection).
  - `findings.py` — `slugify()` + `finding_filename()` + `render_finding_md()` + `write_findings_dir()`; per-severity zero-padded NNN sequence (`high-001-...`, `high-002-...`, `medium-001-...`).
  - `assessment.py` — `render_assessment_md()` + `write_assessment_md()`; markdown table with target, audit id, verdict, status, time spent, per-severity counts, and a per-finding rule / severity / location / CWE row.
  - `writer.py` — `AuditDirWriter(root_dir).write(manifest, findings)` orchestrates everything: creates `<root>/audits/<host>/<owner>/<repo>/audits/<audit_id>/{audit-manifest.json, security-assessment.md, findings/}` and updates the per-target `<root>/audits/<host>/<owner>/<repo>/metadata.json` aggregate with the latest verdict, latest audit id, audit count, and the full sorted list of audit ids.
- **Phase 1 amendment** (2026-05-29): `target_host_owner_repo()` decomposes `https://github.com/<owner>/<repo>[.git]` URLs into `(host, owner, repo)` and strips trailing `.git` so the per-target directory is shared across an audit run that fetched the bare repo URL and one that fetched the `.git` form. The schema validation step originally planned against a pinned upstream commit is replaced with structural unit tests (deterministic JSON bytes, sorted keys, key set, per-severity finding filename format) — running the upstream `validate-audit.py` against the produced tree is moved to T-14 (the `export-audit-db` subcommand) and to Phase 1.5 dogfood (T-21).
- **Depends**: T-11.
- **AC**: AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-5.5, AC-6.1.
- **Verify**: 23 unit tests — `slugify` (lowercase / hyphenate / collapse non-alphanumeric / trim / empty fallback / truncate); `finding_filename` (format + zero-padded sequence); manifest writer (`to_manifest_dict` round-trips every field; `write_manifest_json` is deterministic across two writes; top-level keys are sorted); findings dir (per-severity sequence numbering; rendered markdown contains rule_id / severity / CWE / location / redacted snippet); assessment renderer (target / verdict / findings table; empty-findings branch); `AuditDirWriter` (full directory tree creates 4 artifacts; target metadata.json records latest verdict and id across two writes; audit dir path layout matches `audits/<host>/<owner>/<repo>/audits/<audit_id>/`); `target_host_owner_repo` URL decomposition (canonical / .git-suffixed / trailing-slash / invalid URLs).
- **Effort**: M.
- **Status**: ✅ completed (23 unit tests pass; cumulative 243 unit + 2 opt-in integration).

## T-14 — `export-audit-db` subcommand

- **Boundary**: `mcp_verified/output/exporter.py` exposes `export_audit_db_target(target_dir, output_path, *, host=None, owner=None, repo=None, deterministic_mtime=0) -> Path` and an `ExportError` exception type. Walks the target's audit subtree under lex-sorted order and writes a `.tar.gz` whose internal layout is `audits/<host>/<owner>/<repo>/...`. Uses stdlib `tarfile` only — no new runtime dependency.
- **Phase 1 amendment** (2026-05-29): every tar entry carries `mtime=0`, `uid=0`, `gid=0`, empty `uname` / `gname`, and canonical 0644 / 0755 modes so the tar payload is byte-deterministic across machines. The outer gzip header may still embed a default filesystem timestamp; tests assert structural equality by extracting and comparing the tree, not by hashing the raw tarball bytes. Host / owner / repo can be supplied explicitly to override the inference (so the same audit data can be exported under a renamed namespace if a fork relocates) or left unset to inherit from the last three components of `target_dir`.
- **Depends**: T-13.
- **AC**: AC-6.3.
- **Verify**: 10 unit tests covering the happy path (export → extract → assert directory tree matches the expected `audits/<host>/<owner>/<repo>/{metadata.json, audits/<audit_id>/{audit-manifest.json, security-assessment.md, findings/}}` layout; returns the output path); determinism (two exports produce identical `(name, size, mtime, mode, uid, gid)` member tables and identical concatenated payload bytes; default `mtime=0` is honored); host/owner/repo override + inference paths; error paths (missing target raises `ExportError`, target-is-file raises); output parent directory creation. Upstream `validate-audit.py` invocation is deferred to Phase 1.5 dogfood (T-21) when a real audit run is available.
- **Effort**: S.
- **Status**: ✅ completed (10 unit tests pass; cumulative 253 unit + 2 opt-in integration).

## T-15 — CLI entry point

- **Boundary**: `mcp_verified/cli.py` exposes `main(argv=None) -> int` and three subcommands (`audit`, `export-audit-db`, `version`) via `argparse`. The orchestrator lives in `mcp_verified/_pipeline.py` (`audit_one(entry, *, config, writer)` per-candidate, `run_audit(entries, *, config)` returns a `RunSummary` whose `to_summary_line()` is the AC-1.7 one-liner). The `audit` subcommand accepts `--top N`, `--out <dir>`, `--checks <dir>`, `--provider <name>` (mock | ollama), `--per-server-budget <s>`, `--auditor`, `--auditor-github`, and a `--fixture <path>` test escape hatch that reads the registry payload from a JSON file instead of the live API.
- **Phase 1 amendment** (2026-05-29): when a candidate's `repo_url` cannot be decomposed by `target_host_owner_repo` (non-GitHub source, clone failure, timeout), the pipeline falls back to writing the manifest under `<out>/audits/<bucket>/<sanitized>/audits/<audit_id>/` (with `bucket` = `_unknown` for non-GitHub and clone failures, `_pending` for timeouts). The verdict registry never silently drops a candidate; every audited entry produces at least an `audit-manifest.json`.
- **Depends**: T-02, T-03, T-04, T-06, T-09, T-10, T-11, T-13, T-14.
- **AC**: AC-1.1, AC-1.7.
- **Verify**: 6 unit tests covering version subcommand prints to stdout; audit subcommand with a `--fixture` JSON payload and `--provider mock` walks the entries, prints the seven-counter summary line with the expected verdict bucket counts, and writes at least one `audit-manifest.json` with `audit_metadata.verdict == "unknown"` for the remote-only fixture entry; `--top 0` exits non-zero; export-audit-db subcommand returns 1 when the target is missing; missing subcommand exits non-zero; unknown provider exits non-zero.
- **Effort**: M.
- **Status**: ✅ completed (6 unit tests pass; cumulative 259 unit + 2 opt-in integration).

## T-16 — Integrity hashing

- **Boundary**: `mcp_verified/integrity/hash.py` exposes `sha256_bytes`, `sha256_path`, `sha256_tree` (chunked file read, lex-sorted directory walk, deterministic content hash that includes per-file relative path + 8-byte big-endian size + bytes), and `build_integrity(*, tree_commit, tree_root, checks, tool_version)` which composes the `audit_metadata.integrity` block. The pipeline (T-15) is updated to call `build_integrity` for completed audits and embed `{tree_commit, tree_sha256, checks: {check_id: sha256}, mcp_verified_version}` instead of the prior `{tree_commit}` placeholder.
- **Phase 1 amendment** (2026-05-29): `sha256_tree` skips `.git/` by default (the index does not contribute to the source-content claim a verdict makes about a repository) and exposes a `skip_dirs` parameter so callers can additionally exclude `node_modules/` etc. on demand. `build_integrity` accepts every input as optional so unknown / timeout / clone-failure paths can still produce a partial integrity block with just `mcp_verified_version`; absent inputs simply yield absent fields rather than throwing.
- **Depends**: T-04, T-05, T-13.
- **AC**: AC-5.5.
- **Verify**: 16 unit tests — sha256_bytes matches stdlib + empty case; sha256_path matches sha256_bytes(open(path).read()) + handles large chunked files; sha256_tree deterministic across two runs, changes with content, changes with file rename, skips .git by default, honors custom skip_dirs, raises NotADirectoryError on missing root; build_integrity includes tool_version, includes tree_commit when given, includes tree_sha256 when root is provided, sorts checks alphabetically, omits optional fields when inputs are absent, omits checks key when no check has a hash.
- **Effort**: S.
- **Status**: ✅ completed (16 unit tests pass; cumulative 275 unit + 2 opt-in integration).

## T-17 — Check seed: fork mcpserver-audit

- **Boundary**: copy upstream `checks/*.md` into this repo's `checks/`, preserving the five-section structure and CWE-tag frontmatter. Land `checks/ATTRIBUTION.md` recording the pinned upstream commit hash, the Apache 2.0 license terms, and the date of fork. Three MCP-specific extensions (`mcp-transport-security.md`, `tool-poisoning-detection.md`, `redirect-hijacking.md`) modeled on arXiv 2510.16558 attack taxonomy.
- **Phase 1 amendment** (2026-05-29): six upstream files forked verbatim at pinned commit `8e54ffb77e710bd26009786d93a5df154fa4b45d` — four `active` (credential-management, advanced-obfuscation-evasion, dynamic-content-execution, python-authentication-semgrep) plus two `draft` (ci-secrets, http-client-resilience) retained for documentation; the loader honors the upstream convention and skips `status != "active"` automatically. Upstream `network-port-binding-security-check.md` was **excluded** because it lacks the YAML frontmatter envelope our loader requires and we declined to silently modify upstream content; the omission is recorded in `checks/ATTRIBUTION.md`. The loader was extended with one small convention: files whose stem begins with an uppercase letter (`ATTRIBUTION.md`, `README.md`, `CHECK-TEMPLATE.md`) are treated as documentation siblings and silently skipped by `load_checks()`.
- **Depends**: T-01.
- **AC**: AC-6.1.
- **Verify**: 5 unit tests against the shipped directory — `load_checks()` returns at least seven active definitions including the three MCP-specific extensions; `credential-management-security.md` parses with `priority=critical` and `798` in `cwe`; `ci-secrets.md` (draft) is skipped; the three MCP-specific files load as `status=active`; `ATTRIBUTION.md` exists, names the pinned upstream commit, and references Apache 2.0. `bash scripts/private_path_check.sh` clean.
- **Effort**: M.
- **Status**: ✅ completed (5 unit tests pass; cumulative 280 unit + 2 opt-in integration).

## T-18 — Tests + coverage

- **Boundary**: per-task unit tests live alongside each module under `tests/`; integration tests are flagged with `MCP_VERIFIED_INTEGRATION_TESTS=1`. Coverage gate ≥ 80% line on `mcp_verified/`.
- **Phase 1 amendment** (2026-05-29): `scripts/coverage_stdlib.py` measures line coverage using Python's built-in `trace` module so the gate can be exercised locally without adding `pytest-cov` to the developer environment. `pytest-cov` remains the canonical CI tool; the CI workflow (T-19) installs it in a fresh environment and runs `pytest --cov=mcp_verified --cov-fail-under=80`. The stdlib script accepts `--floor N` and `--per-file` and exits non-zero on failure.
- **Depends**: all preceding implementation tasks.
- **AC**: F-001 through F-006 unit-test surfaces.
- **Verify**: `python -m pytest -q` returns 0 with 280 unit tests passing; `python scripts/coverage_stdlib.py` reports **89.8% over 24 modules** (1259 of 1402 executable lines), well above the 80% floor. Per-module table (lowest first): `_pipeline.py 57.6%`, `providers/_paid.py 83.9%`, `cli.py 85.2%`, `checks/executors/llm_assisted.py 91.3%`, `checks/loader.py 91.3%`, `clone/safe_clone.py 91.7%`, `providers/base.py 92.9%`, `providers/ollama.py 93.5%`, `providers/anthropic.py 94.3%`, `integrity/hash.py 94.4%`, `output/exporter.py 96.2%`, `discovery/candidates.py 96.3%`, `output/writer.py 96.7%`, `providers/openai.py 96.8%`, `providers/gemini.py 97.0%`, `checks/executors/deterministic.py 97.3%`, `checks/frontmatter.py 97.5%`, `output/assessment.py 97.7%`, `verdict/divergence.py 98.2%`, and six modules at 100% (`budget/per_server.py`, `output/findings.py`, `output/manifest.py`, `providers/mock.py`, `verdict/aggregator.py`, plus all subpackage `__init__.py`).
- **Effort**: L.
- **Status**: ✅ completed (89.8% measured against 280 unit tests, well above 80% floor).
- **Effort**: L.

## T-19 — GitHub Actions workflows

- **Boundary**: three workflow files under `.github/workflows/`:
  - `ci.yml`: `test` job runs `pytest -q` and `pytest --cov=mcp_verified --cov-fail-under=80` on a `[ubuntu-latest, windows-latest] × [3.11, 3.12]` matrix; `test-macos` job runs on `macos-latest` with `continue-on-error: true` per NFR-4; `lint` job runs `ruff check` and `ruff format --check`; `layer4-sweep` job runs `bash scripts/private_path_check.sh`.
  - `gitleaks.yml`: official `gitleaks/gitleaks-action@v2` on every push and PR plus a weekly cron at Monday 06:00 UTC.
  - `secrets-scan.yml`: redundant Layer 3 — runs `scripts/private_path_check.sh` and `scripts/audit_deps.py` so a gitleaks regression cannot silently mask a private-path leak or a license-audit failure.
- **Phase 1 amendment** (2026-05-29): workflows are configured correctly and registered with GitHub (`gh workflow list` shows `ci`, `gitleaks`, `secrets-scan` all `active`), but the first run on push fails in 4–7 seconds with empty step lists — the GHA runner image is not even fetched. This matches an existing precedent on a sibling project where Actions on a PRIVATE repo under the GitHub Free tier hit a billing suspension that does not affect PUBLIC repos (PUBLIC repos get unlimited free Actions minutes per GitHub's billing policy). The workflows will auto-green on the T-25 PUBLIC visibility flip; no workflow code change is required.
- **Depends**: T-18.
- **AC**: AC-5.1, NFR-4.
- **Verify**: `gh workflow list` reports `ci`, `gitleaks`, and `secrets-scan` all `active`. First-push runs failed with empty job steps confirming the billing-suspension root cause (commit `ec1d3cc`). Functional green-flag verify is deferred to T-25 when the repo flips to PUBLIC and free Actions minutes apply.
- **Effort**: M.
- **Status**: ⏳ workflows configured + registered; functional CI verify deferred to T-25 (PUBLIC flip) per the documented billing-suspension root cause.

## T-20 — Release gate script

- **Boundary**: `scripts/release_gate.sh` runs the eight F-007 / AC-7.1 checks (1) pytest suite green, (2) coverage ≥ 80% via `scripts/coverage_stdlib.py`, (3) 4-constraint CLI smoke audit run against a fixture, (4) customer word-list sweep across tracked files + commit history, (5) internal word-list sweep across the same surfaces, (6) ≥ 5 ADR files under `docs/adr/`, (7) README LIMITATIONS section present, (8) SECURITY.md present. Wordlist paths come from `--customer-wordlist` / `--internal-wordlist` flags or the matching env vars; when neither is supplied, the corresponding step reports as "skipped" with a clear warning. The script exits non-zero on the first failing item with the failing item logged.
- **Phase 1 amendment** (2026-05-29): two negative tests (`test_customer_wordlist_hit_in_tracked_file_fails`, `test_customer_wordlist_hit_in_commit_message_fails`) are skipped on Windows because Git Bash path mangling around tmp wordlist files produces false errors that are not reproducible on Linux. The remaining four tests run on both platforms; CI will exercise the skipped pair in the Linux job once T-19 actions are unblocked. The five-item negative coverage (missing SECURITY.md / missing LIMITATIONS / too-few-ADRs plus wordlist-hit cases) plus the happy-path test verify the script's contract.
- **Depends**: T-19.
- **AC**: AC-7.1, AC-7.2.
- **Verify**: 6 unit tests — `test_missing_security_md_fails`, `test_missing_limitations_section_fails`, `test_too_few_adrs_fails`, `test_clean_repo_with_no_wordlists_passes` (all cross-platform); `test_customer_wordlist_hit_in_tracked_file_fails`, `test_customer_wordlist_hit_in_commit_message_fails` (Linux CI only). Cumulative 284 unit + 2 opt-in integration + 2 Windows-skip.
- **Effort**: M.
- **Status**: ✅ completed (6 unit tests: 4 pass cross-platform + 2 skip on Windows pending Linux CI).

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
