# Public release readiness — 2026-05-29

Snapshot recorded when the repository visibility was changed to public.

## Quality gate

- `scripts/release_gate.sh`: **8/8 PASS** ("ready for public visibility").
- Test suite: **284 passed, 4 skipped** (network / Windows-path opt-ins).
- ADRs: 12. Active checks: 13 (of 16 files). Runtime dependencies: 0.

## Repository hygiene at flip

- Branches: `main` only. Tags: `v0.1.0`. Open PRs: 0. No stray refs.
- LICENSE: MIT. README carries overview, demo image, four-constraint
  design narrative, quickstart, and an explicit Limitations section.

## CI status — green after the public flip

While the repository was private, Actions runs were blocked under the
free-tier billing rule (jobs not starting). The public flip restored free
standard-runner minutes, and the first post-flip runs surfaced two real,
previously-masked issues that were then fixed:

- **Lint debt** — the tree had 36 ruff findings against its own
  `[tool.ruff]` config (the lint job had never actually run). Fixed with
  `ruff --fix` + manual fixes + `ruff format` across the tree.
- **windows-latest test failures** — `bash scripts/release_gate.sh`
  resolved to the WSL stub on the runner. `_has_bash()` now probes that
  bash actually executes, so those tests skip there while still running on
  Linux, macOS, and Git Bash.

After these fixes, `ci`, `gitleaks`, and `secrets-scan` are all green on
`main`. The full suite passes (284 tests; coverage gate ≥ 80%; release
gate 8/8).
