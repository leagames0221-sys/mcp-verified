# ADR-012 — Schema-hash diff as the canonical detection signal for the "rug-pull" tool-mutation class

## Status

Accepted, 2026-05-29.

## Context

The "rug-pull" attack class against MCP servers was formalised in
arXiv preprint 2506.01333 (Bhatt / Narajala / Habler — Enhanced Tool
Definition Interface) and empirically demonstrated by the Postmark MCP
incident of September 2025 (v1.0.16 silently appended a BCC header to
exfiltrate ~3000–15000 emails/day from ~300 organisations before npm
takedown).

Rug-pull works because MCP clients do not verify the **constancy** of
a server's tool definitions across requests. A well-behaved tool
definition is approved by the user once and then trusted; the server
can subsequently mutate the tool's description, input schema, or
implementation behaviour to inject credential-exfiltration parameters
or coerce the consuming agent into executing instructions that the
original definition did not advertise. The mutation may persist for
seconds (deniable) or for the lifetime of the session, and the
consuming agent has no built-in mechanism to notice.

The detection question is therefore: **what canonical signal can a
batched audit emit so a consumer knows a server may rug-pull, given
that the audit cannot legitimately probe the live server in Phase 1?**

The deep-research probe of 2026-05-29 (evidence file
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`) confirms
that the ETDI proposal targets the same gap and that no widely-adopted
detection tooling exists today beyond the proposal itself. This is a
green-field area where `mcp-verified` can contribute a defensible
signal.

Options considered:

- **Source-level mutability inspection only.** Flag servers whose
  source code constructs tool definitions from runtime-mutable state
  (database lookup, network fetch, environment variable injected after
  startup). Cheap; no probing required. Catches the structural
  precondition but does not detect actual mutation. Useful as Phase 1
  signal but not sufficient as a final claim.
- **Live `tools/list` polling with SHA-256 diff.** Connect to the
  server, capture `tools/list`, hash the canonicalised JSON, repeat,
  diff. Definitive but requires a dynamic-probe stage and therefore
  inherits ADR-010's full sandbox doctrine. Out of scope for Phase 1;
  in scope once ADR-010's preconditions are satisfied.
- **Hybrid: static inspection in Phase 1, schema-hash diff once dynamic
  probing exists.** Same signal name on both paths so consumers see a
  coherent finding type whose evidence basis improves over time.
  Accepted.

## Decision

The canonical detection signal for the rug-pull class shall be a
**schema-hash diff** between two observations of the same server's
`tools/list` response, where the hash is computed over a canonicalised
JSON serialisation of the response.

Phase 1 ships **the static-inspection fallback** under
`checks/tool-schema-mutation-rug-pull-check.md`. The static check:

1. Inspects the candidate's source for tool-definition construction
   sites and flags those that derive a tool's `name`, `description`,
   `inputSchema`, or `annotations` from runtime-mutable state
   (database fetch, network call, environment variable read after
   process start, file read on a path the server writes to itself,
   etc.).
2. Emits a `rug-pull-precondition` finding when the structural
   precondition is present.
3. Honestly documents in its `## Risk Evaluation` section that
   "the static check detects the precondition; observing the actual
   mutation requires the dynamic-probe stage governed by ADR-010,
   which Phase 1 does not yet ship."

A **future dynamic-probe stage** (subject to ADR-010's sandbox
doctrine) shall implement the full schema-hash diff per these rules:

1. Canonicalisation: the captured `tools/list` response is normalised
   by sorting object keys lexicographically at every depth,
   serialising with `json.dumps(..., separators=(',', ':'), sort_keys=True,
   ensure_ascii=False)`, and encoding as UTF-8.
2. Hash: SHA-256 of the canonicalised byte sequence.
3. Sampling: at least N=3 observations spaced ≥30 s apart within a
   single audit run. Sampling continues until either (a) all
   observations agree, or (b) the per-server wall-clock budget is
   exhausted.
4. Reporting: if any two observations disagree, emit a
   `rug-pull-mutation-observed` finding with severity `critical`,
   recording both hashes and a unified diff of the canonicalised
   JSON. If all observations agree but the structural precondition
   (Phase 1 static check) was present, emit a
   `rug-pull-precondition-only` finding with severity `medium`.
   If neither, emit no rug-pull-related finding.
5. Schema versioning: the canonicalisation rules above shall be
   pinned in `audit-manifest.json` under
   `audit_metadata.rug_pull_canonicalisation_version`. A change to
   the rules requires an ADR amendment so consumers of the verdict
   registry can detect when historical hashes are not comparable.

## Consequences

**Positive**:

- A single canonical signal name (`rug-pull-precondition` →
  `rug-pull-precondition-only` → `rug-pull-mutation-observed`) means a
  downstream consumer can track the severity-progression as audit
  capability grows. The same finding type means the same thing
  whether it came from the static path or the dynamic path; only the
  evidence basis differs.
- Canonicalisation rules pinned by version number make historical
  audits comparable. A registry consumer can ask "which servers'
  hashes changed between audit-2026-Q2 and audit-2026-Q3?" without
  worrying that a serialisation tweak invalidated the comparison.
- Sets a defensible green-field claim for the project: rug-pull
  detection is a known-gap area per the ETDI proposal, and shipping
  a canonical signal here is something a strong-hire reviewer can
  point at as non-derivative.

**Negative**:

- The static-inspection-only Phase 1 signal will produce false
  positives (a runtime-mutable source pattern does not prove
  mutation happens). The check definition shall make this honest
  in its `## Risk Evaluation`.
- The full dynamic check requires ADR-010's sandbox to land first.
  Until then, the canonical signal is observable in name only; the
  evidence basis is structural.
- Canonicalisation rules are a one-way door: changing them invalidates
  all historical hashes. The schema-versioning field exists to make
  the breakage visible, but it does not avoid the migration cost.

**Neutral**:

- The check's MCP-protocol category alias (per ADR-011) is `rug-pull`.
  No new category slug is required.
- The ETDI proposal itself is preprint-stage (not peer-reviewed); the
  Postmark MCP incident is the empirical anchor that justifies
  shipping detection today rather than waiting for academic
  consensus.
