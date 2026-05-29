---
title: Supply Chain Maintainer-Graph Blast-Radius Inspection
version: 1.0
date: 2026-05-29
tags: [security, MCP, supply-chain, maintainer-graph, shai-hulud]
aliases: [maintainer-blast-radius, npm-maintainer-graph, sibling-package-risk]
status: active
priority: medium
cwe: [506, 829]
cwe-primary: 506
vulnerability-db: []
---

# Supply Chain Maintainer-Graph Blast-Radius Inspection

## Purpose

For each MCP server candidate published to npm, enumerate the
candidate maintainer's other published packages and surface the
**blast radius** — the count and namespace of sibling packages that
inherit the same trust boundary. A single compromised npm
maintainer token is, since the Shai-Hulud worm, a multi-package
incident by default: the worm enumerates `maintainer:` siblings via
the npm search API and republishes each one with a poisoned payload.

This check is **added in this fork; not upstream** — it is grounded in
the deep-research probe of 2026-05-29 recorded under
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-2.
Primary evidence: Unit42's analysis of Shai-Hulud, which documents
that "the worm uses the stolen token to enumerate the maintainer's
other packages via the npm `maintainer:` search filter and
republishes them poisoned."

## Why This Matters

A consumer evaluating an MCP server package usually inspects that
package alone. Shai-Hulud demonstrated that the relevant trust
boundary is not the package — it is the **maintainer's entire
publishing portfolio**. A small package with a careful auditor
might still be a Shai-Hulud vector if it shares a maintainer with
a high-traffic dependency that the worm has already poisoned.

This check produces an **informational** finding (severity: `low`
to `medium` depending on the sibling count) rather than a `risky`
verdict on its own. The signal is meant to be combined with the
`supply-chain-preinstall-hook-check` and the
`credential-management-security` checks; high blast radius alone is
not a defect, but high blast radius combined with any other signal
elevates the overall verdict.

## For AI Assistants: Automated Analysis

### Maintainer Enumeration (Live Probe; Phase 1.5 Network-Allowlisted)

The npm registry exposes a maintainer-search API:

```text
GET https://registry.npmjs.org/-/v1/search?text=maintainer:<MAINTAINER>&size=250
```

For each maintainer listed in the candidate's `package.json`
`maintainers` field (or, if absent, the `author` field), issue this
request and count the returned packages. The endpoint is allowlisted
in `mcp-verified`'s default network policy because it returns
public registry metadata only and does not require credentials.

```python
# Pseudocode — the actual implementation belongs in the check runner,
# not in the check definition file, because runtime registry calls are
# orchestrator concerns.
def maintainer_blast_radius(maintainer_handle: str) -> int:
    response = http_get(
        f"https://registry.npmjs.org/-/v1/search"
        f"?text=maintainer:{maintainer_handle}&size=250"
    )
    return response.json().get("total", 0)
```

### Severity Bands

| Sibling count | Severity | Notes |
|---|---|---|
| 1 (this package only) | informational | Single-package maintainer; minimal blast radius. |
| 2–9 | low | Small portfolio; combined-signal weight increases. |
| 10–49 | medium | Moderate portfolio; recommend reviewing the top three siblings' popularity. |
| 50+ | medium-high | Large portfolio; a single token compromise has wide reach. Combined-signal weight increases markedly. |

### GitHub-Side Provenance Cross-Check

In parallel with the npm-side blast radius:

1. **Repo age** — `gh repo view <owner>/<repo> --json createdAt`
   compared to the npm publish date. A package published within
   hours of the GitHub repo's creation is a typosquat / fake-fork
   signal (SmartLoader Oura clone TTP — see evidence file § F-2).
2. **Contributor profile heuristics** — for each contributor on the
   GitHub repo, query `/users/<login>/events` and look for AI-generated
   account signatures (account < 90 days old + entirely commit
   activity + no issue interaction). ≥5 such contributors is a
   `medium-high` informational finding.

## For Humans: Manual Assessment Steps

1. Open the candidate package on <https://www.npmjs.com> and click the
   maintainer's profile. Count the listed packages.
2. Scan the top three sibling packages by weekly download count and
   check whether they ship `preinstall` / `install` hooks
   (cross-reference with `supply-chain-preinstall-hook-check`).
3. Open the candidate's GitHub repo and click "Contributors". For
   each contributor with > 5% commit share, briefly inspect the
   contributor's profile — empty issue history with very recent
   account creation is the SmartLoader fingerprint.

## Risk Evaluation

This check produces **informational** findings by design. The
finding is consumed by the verdict aggregator alongside other
signals; on its own, high blast radius is the cost of working with
prolific maintainers (many of whom are entirely legitimate and
high-trust). The signal becomes consequential when combined with:

- An install-hook finding from `supply-chain-preinstall-hook-check`
  (the worm's most common payload site).
- A credential-leak grep hit from `credential-management-security`
  (especially `.npmrc` token shapes — the worm's harvesting target).
- A fake-contributor-ecosystem signal from the GitHub-side checks
  documented above (the typosquat / Oura clone TTP).

A `verified` verdict is permitted with high blast radius alone; a
`caution` or `risky` verdict requires at least one second signal.

## MCP-Protocol Category Mapping (per ADR-011)

`aliases: [supply-chain, maintainer-graph]` — touches the **Supply
Chain** category. Like the install-hook check, this is upstream of
the MCP protocol itself.

## Remediation Guidance

For maintainers receiving this signal on their own packages:

- Rotate the npm token used to publish each affected package.
- Enable npm 2FA on the maintainer account (Classic plan and above).
- Consider provenance attestations (`npm publish --provenance`,
  GitHub Actions OIDC) so consumers can verify the package was
  built from the public repo's HEAD.

For consumers:

- Prefer MCP server packages whose maintainer publishes a small,
  closely-related portfolio over packages whose maintainer
  publishes dozens of unrelated utilities.
- Pin lockfiles by SHA-256 integrity, not by semver range.

## References

- Unit42 — npm supply-chain attack analysis:
  <https://unit42.paloaltonetworks.com/npm-supply-chain-attack/>
- npm Search API documentation:
  <https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md#get-v1search>
- Project evidence file: `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-2

---

*This check is added in this fork; not upstream. Maintained as part of
`mcp-verified` under MIT licence; see `LICENSE` and `checks/ATTRIBUTION.md`.*
