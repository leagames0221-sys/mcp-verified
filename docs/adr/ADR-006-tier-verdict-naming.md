# ADR-006 — Tier verdict naming: `verified` / `caution` / `risky` / `unknown`

## Status

Accepted, 2026-05-28.

## Context

Each audited server gets a single top-level verdict. The naming affects how reviewers read the output, how downstream consumers filter the verdict registry, and whether the verdict reads as an honest summary or an overclaim.

Two naming axes considered:

- **Star tiers (★★★ / ★★ / ★ / ?)** — compact, ordinal, common in review aggregator UX.
- **Plain words** (e.g., `verified` / `caution` / `risky` / `unknown`) — more explicit, less ordinal, no ranking semantics.

The portfolio's quality rubric is explicit that ordinal star ratings tend to drift into overclaim ("this is a ★★★ project") unless the rubric criteria are themselves binary and checked literally. Verdicts written about other people's repositories are a more sensitive case: a tier verdict on someone else's code is a public claim, and ordinal compactness ("4-star auth, 2-star supply chain") invites a precision the underlying checks do not earn.

## Decision

Phase 1 top-level verdict is one of four **plain-word values**:

- **`verified`** — Audited against the configured check set; no high-severity findings; LLM-assisted review (when used) did not flag any concerns.
- **`caution`** — Audited; at least one medium-severity finding, no high-severity. Reviewer should read the assessment before adopting.
- **`risky`** — Audited; at least one high-severity finding. Adoption is discouraged without remediation.
- **`unknown`** — Audit could not complete (source unreachable, candidate is not on GitHub, per-server budget exhausted, or all checks errored out). The verdict carries no claim about the underlying server.

These map cleanly to the `audit-db` `findings_summary` severity counts and require no extra schema fields.

The README documents that a `verified` verdict means "passed the published Phase 1 check set against this commit hash, given the configured provider"; it does not mean "no vulnerability exists" (NFR-5 honest framing).

## Consequences

**Positive**:

- Plain-word verdicts read honestly. A `verified` verdict cannot easily be misread as "audited by humans, certified for production" — the README explicitly disclaims that interpretation.
- Mapping to severity counts is one function, deterministic and inspectable.

**Negative**:

- Compact UI (e.g., "tier 4 servers only") requires a UI-layer mapping; we don't ship that mapping in Phase 1. Downstream consumers can compute their own.
- Some users will still want ordinal ranking; we explicitly do not provide it.

**Neutral**:

- Phase ≥ 2 could add a numeric AIVSS score per finding (orthogonal to the top-level verdict); ADR-006 does not preclude that.
