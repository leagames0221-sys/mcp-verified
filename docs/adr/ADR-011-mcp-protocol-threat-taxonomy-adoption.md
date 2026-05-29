# ADR-011 — Adopt the MCP-protocol threat taxonomy as design inspiration, not as a sealed check schema

## Status

Accepted, 2026-05-29.

## Context

Phase 1 ships a check seed forked from `mcpserver-audit` (ADR-007) plus
three MCP-specific extensions (`mcp-transport-security`,
`tool-poisoning-detection`, `redirect-hijacking`) modelled on the Li
and Gao arXiv paper. As Phase 1 closed, the deep-research probe of
2026-05-29 (evidence file `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`)
surfaced two upstream taxonomies that this project's check set should
acknowledge structurally rather than ad-hoc:

- **The `mcpserver-audit` six-category taxonomy** (Prompt Injection,
  Confused Deputy, Token Theft, Data Exfiltration, Protocol Violations,
  Cross-Origin Issues). The upstream README presents these as
  "Expert Knowledge Areas" — an educational frame, not a sealed test
  matrix. The actual `/checks` directory does not map 1:1 to the six
  categories.
- **The `mcp-scan` (Invariant Labs) check matrix**, which advertises
  detection of "15+ distinct security risks" including Prompt
  Injection via tool descriptions, Tool Poisoning, Tool Shadowing, and
  Toxic Flows. The matrix is implementation-driven; the categories
  shift as new attacks are added.

Both taxonomies are genuinely useful as design references — they make
the space of MCP-specific threats visible at a glance and they give a
reviewer a vocabulary for finding gaps. Neither is appropriate as a
sealed check schema that `mcp-verified` claims to implement in full,
because:

1. The upstream framing itself is "educational" and not stable; locking
   our check set to it commits us to track changes that may be
   pedagogical rather than substantive.
2. Several categories (Confused Deputy, Cross-Origin Issues) require
   dynamic probing to detect meaningfully; today's read-only static
   path can only flag suggestive structural signals, which is honest
   but not the same as "covers Confused Deputy".
3. Honest framing matters more than coverage marketing. Claiming
   "covers the six categories" when the implementation flags three of
   them suggestively is the kind of claim that the
   `README.md > Limitations and honest framing` posture exists to
   prevent.

Options considered:

- **Adopt the six-category taxonomy as the formal check schema.**
  Strong narrative ("aligned with CSA project taxonomy"). Weak honesty
  cost: implies coverage the static path cannot deliver. Rejected.
- **Adopt `mcp-scan`'s 15-risk matrix as the formal check schema.**
  Same problem at higher magnitude — the matrix changes; coverage
  would be a moving target. Rejected.
- **Adopt both taxonomies as design inspiration, document the partial
  mapping honestly, and let the check set evolve check-by-check on
  evidence.** This is what we already do informally; ADR-011 makes it
  the explicit policy and writes down the mapping so reviewers do not
  have to reconstruct it. **Accepted.**

## Decision

`mcp-verified` adopts the `mcpserver-audit` six-category taxonomy and
the `mcp-scan` check matrix as **design inspiration**, not as a
formal check schema. The following rules apply:

1. **Each shipped check declares which taxonomy categories it
   suggestively touches**, in its frontmatter `aliases` block, using
   stable category slugs (`prompt-injection`, `tool-poisoning`,
   `tool-shadowing`, `rug-pull`, `confused-deputy`, `token-theft`,
   `data-exfiltration`, `protocol-violation`, `cross-origin`,
   `transport-misconfig`, `credential-leak`, `supply-chain`,
   `command-injection`, `token-lifecycle`). A category may be touched
   by zero, one, or several checks. **No claim of full coverage** is
   made for any category.
2. **`docs/evidence/` records the taxonomy snapshot.** When a new
   upstream taxonomy revision is observed, the relevant evidence file
   is amended; ADR-011 is not amended unless the project's stance on
   adoption-vs-schema-claim changes.
3. **Coverage gaps are documented in `README.md > Limitations`**, not
   hidden. If a category is touched by zero shipped checks, the README
   shall name it and explain why (typically: requires dynamic probing
   that ADR-003 forbids in Phase 1).
4. **Marketing copy is constrained.** Phrases like "covers the CSA
   six categories" or "implements the `mcp-scan` matrix" shall not
   appear in any public artefact (README, post-PUBLIC-flip
   announcements, or contributed `audit-db` PR descriptions). The
   honest phrasing is "draws on the `mcpserver-audit` taxonomy as
   design inspiration; per-check coverage is documented in each
   check's `aliases` block."
5. **The "rug-pull" threat class** (Postmark MCP empirical realisation;
   ETDI proposal in arXiv 2506.01333) gets its own dedicated check
   under ADR-012 — `tool-schema-mutation-rug-pull-check.md`. Because
   rug-pull requires session-spanning observation, ADR-012 documents
   the static-analysis fallback (declare-only inspection) and reserves
   the full implementation for the dynamic-probe phase governed by
   ADR-010.

## Consequences

**Positive**:

- The relationship between this project's check set and the upstream
  taxonomies is explicit and auditable. A reviewer can read each
  check's `aliases` block and assemble a coverage matrix without
  trusting a marketing claim.
- Honest framing is enforced structurally, not by hope. The "no
  full-coverage claim" rule is in the ADR, not just in a one-off
  guidance doc.
- New upstream taxonomy revisions cost a small evidence-file amend,
  not a check-schema refactor. The project's velocity is preserved.

**Negative**:

- The narrative is less catchy than "implements CSA taxonomy in full".
  Specifically, a casual reader who scans the README for "covers X
  threat" headlines will see fewer of them than competitors that
  over-claim. The trade-off is intentional — the project's M5
  (honest disclosure) posture is non-negotiable.
- Every check author now has to think about category tagging. The
  category slug list above is the controlled vocabulary; adding a new
  slug requires an ADR amendment.

**Neutral**:

- The category slug list will grow over time as new attack classes are
  documented. Each addition belongs in a small amendment to this ADR
  rather than in a churn-prone separate registry.
