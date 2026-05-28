# ADR-008 — Phase 1 popularity signal: registry recency only

## Status

Accepted, 2026-05-29.

## Context

T-03 (`mcp_verified/discovery/candidates.py`) ranks the registry inventory to select the Phase 1 top-N audit candidates. The TASKS.md T-03 draft proposed a `GitHub stars × log10(downloads) with a freshness penalty` formula.

A probe of the live registry's first 10 entries on 2026-05-29 (recorded under `docs/evidence/2026-05-29-registry-no-popularity-signal-probe.md`) established that the registry response carries **no popularity field at all** — no downloads, no stars, no installs, no dependents. The only ranking-eligible fields are timestamps (`publishedAt`, `updatedAt`), `status`, and `isLatest`.

Realizing the drafted formula therefore requires at least one of:

- A GitHub API call per candidate to fetch stargazer counts.
- An npm / PyPI API call per candidate carrying a `packages` entry (none observed in the first-page sample).

Both options expand network surface beyond what T-03's half-day effort budget supports cleanly, introduce rate-limit failure modes, and add test-fixture complexity.

## Decision

Phase 1 uses a **registry-recency-only deterministic score**, formula version `phase1-v1`:

```
score(entry) = 1.0 / (1.0 + days_since(updatedAt) / 30.0)
```

with the candidate set filtered to `is_latest == true AND status == "active"`, and ties broken by lexicographic order on `name`. The formula is pinned in `mcp_verified/discovery/candidates.py` as the constant `SCORE_FORMULA_REVISION = "phase1-v1"`; any change to either the score function or the filter requires bumping that constant and recording the bump in `audit-manifest.json` `audit_metadata.tools_used`.

GitHub API enrichment (`api.github.com/repos/<owner>/<repo>` for stargazers count) and package-registry enrichment (npm / PyPI for downloads) are **deferred** to a follow-up (`T-03b` / Phase 1.5).

## Consequences

**Positive**:

- Pure-function scoring: no extra network surface beyond what T-02 already established, no rate-limit risk, no API token requirement, no extra test fixtures.
- Deterministic: two runs against the same inventory produce identical ordering, which T-03's verify step requires (AC-1.2 reproducibility).
- Honest: the docstring and the README's Limitations section both record that "recency" is not "popularity"; reviewers see the trade-off without surprise.

**Negative**:

- Recency is a weak proxy for popularity. A long-stable, widely-used server may score lower than a recently-published unknown server. Phase 1.5 dogfood probes (B1–B4) will validate whether the top-50 candidates selected this way are actually the servers a reviewer would care about.
- If the registry adds a popularity field upstream before Phase 1.5, this ADR is amended rather than rewritten — the recency-based formula stays as a fallback.

**Neutral**:

- The Phase 1.5 GitHub-enrichment follow-up can layer onto the same `CandidateScorer` API; the formula revision string distinguishes Phase 1 verdicts from Phase 1.5 verdicts in audit manifests.
