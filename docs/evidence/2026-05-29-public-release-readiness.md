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

## Known open item — CI billing

GitHub Actions runs are currently not starting. The run annotations report
an account-level billing block:

> "The job was not started because recent account payments have failed or
> your spending limit needs to be increased."

Public repositories receive free standard-runner minutes, so **no workflow
change is required** — once the account billing is resolved, the configured
`ci`, `gitleaks`, and `secrets-scan` workflows will execute. The full suite
passes locally (284 tests; coverage gate ≥ 80%; release gate 8/8).
