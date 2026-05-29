---
title: Token Lifecycle Policy Inspection
version: 1.0
date: 2026-05-29
tags: [security, MCP, token-lifecycle, OAuth, OWASP-MCP01]
aliases: [token-lifetime, token-rotation, session-token-policy]
status: active
priority: high
cwe: [613, 384, 312]
cwe-primary: 613
vulnerability-db: []
---

# Token Lifecycle Policy Inspection

## Purpose

Surface MCP servers whose declared or implemented token-lifecycle
policy fails the OWASP MCP Top 10 (2025) MCP01 "Token Mismanagement
and Secret Exposure" detection criteria: token lifetimes longer than
session duration, absence of enforced rotation, or token re-use
across sessions without renewal.

This check is **added in this fork; not upstream** — it is grounded in
the deep-research probe of 2026-05-29 recorded under
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-6.
Primary evidence: OWASP MCP Top 10 (2025) MCP01 detection rubric and
mitigation recommendations.

## Why This Matters

MCP servers frequently broker credentials between the consuming agent
and downstream services. Because MCP-based systems often operate
autonomously, a leaked token can grant high-impact permissions without
direct human intervention; a token whose TTL exceeds the session
duration extends the blast radius of any leak far beyond the
operational window. OWASP MCP01 names "token lifetimes are longer
than session duration or lack enforced rotation" as a literal
detection criterion and recommends "token renewal for every new MCP
session" as the canonical mitigation.

The signal is statically inspectable in the majority of cases because
TTL and rotation policy are usually declared in config (
`expires_in`, `max_age`, `rotation_interval`) or in OAuth client
manifests rather than computed at runtime.

## For AI Assistants: Automated Analysis

### Configuration Inspection

```bash
# Locate token TTL / rotation declarations across common formats
grep -rEn "(expires_in|max_age|token_ttl|access_token_lifetime|refresh_token_lifetime|rotation_interval|rotation_policy)\s*[:=]" \
  --include="*.py" --include="*.js" --include="*.ts" \
  --include="*.json" --include="*.yaml" --include="*.yml" \
  --include="*.toml" --include="*.env*" .

# Look for hard-coded long TTLs (≥ 1 day in common units)
grep -rEn "(expires_in|max_age|token_ttl)\s*[:=]\s*(86400|604800|2592000|31536000|[0-9]{6,})" \
  --include="*.py" --include="*.js" --include="*.ts" \
  --include="*.json" --include="*.yaml" --include="*.yml" .

# Detect refresh-token issuance without rotation
grep -rEn "refresh_token" --include="*.py" --include="*.js" --include="*.ts" -A 5 .
```

### Runtime-Code Inspection

```bash
# OAuth handler that issues a token but does not bind it to a session
grep -rEn "(issue_token|create_access_token|sign_jwt|jwt\.encode|jose\.sign)" \
  --include="*.py" --include="*.js" --include="*.ts" -A 8 .

# Look for token persistence sites — disk write of a long-lived token
grep -rEn "(open\(.*['\"]w|fs\.writeFileSync|fs\.promises\.writeFile)\(.*token" \
  --include="*.py" --include="*.js" --include="*.ts" .
```

### Severity Bands

| Observation | Severity |
|---|---|
| TTL > 7 days **and** no rotation declared | high |
| TTL 1–7 days with no rotation | medium |
| TTL > session duration but ≤ 1 day | low |
| Refresh token issued without rotation policy | medium |
| Persistent token written to disk without `chmod 600` equivalent | high |
| No token TTL declaration and no clear default — verify against framework default | informational |

## For Humans: Manual Assessment Steps

1. **Locate the OAuth client manifest** (`oauth-client.json`,
   `client_metadata.py`, or equivalent). Read the `expires_in`,
   `max_age`, and `rotation_*` fields.
2. **Trace the token-issuance code path** from the OAuth callback to
   the response. Is the issued token bound to a session identifier
   or is it free-standing?
3. **Check for documented rotation procedure** in the README or
   `SECURITY.md`. Absence is a finding even when the code looks fine
   — operators of the server need to know how to rotate.
4. **Compare TTL to expected session length.** A token with a 30-day
   TTL serving sessions that average minutes is the OWASP MCP01
   canonical failure pattern.

## Risk Evaluation

A token whose TTL substantially exceeds session duration is a `high`
severity finding under OWASP MCP01 because leaked tokens grant
disproportionately broad access (in the sense OWASP intends: broader
than the operational need warrants — see the project's evidence file
for the precise wording, which is deliberately not over-claimed
here).

A refresh-token issuance path that does not rotate the refresh token
on each use is `medium` severity — leaked refresh tokens become
persistent compromise vectors otherwise.

Absent or unparseable token-lifecycle declarations are
`informational` rather than `medium` because the framework default
may be sound; the finding nudges the reviewer to verify explicitly
rather than asserting a defect that may not exist.

## MCP-Protocol Category Mapping (per ADR-011)

`aliases: [token-lifecycle, token-theft]` — touches the **Token
Lifecycle** and **Token Theft** categories. Does not touch the
session-mutation categories (`rug-pull`, `tool-shadowing`).

## Remediation Guidance

- Bind every issued token to a session identifier and set TTL to the
  session's expected duration. Default to short-lived (minutes,
  not days) access tokens with refresh.
- Implement refresh-token **rotation**: each use of a refresh token
  invalidates the prior one and issues a fresh refresh token.
- Document the rotation procedure in `SECURITY.md`. Operators who do
  not know how to rotate will not rotate.
- For high-sensitivity downstream services, prefer per-session
  ephemeral credentials (workload identity, AWS STS, GCP
  ID-token-exchange) over long-lived tokens persisted to disk.

## References

- OWASP MCP Top 10 (2025) MCP01 — Token Mismanagement and Secret
  Exposure:
  <https://owasp.org/www-project-mcp-top-10/2025/MCP01-2025-Token-Mismanagement-and-Secret-Exposure>
- Project evidence file:
  `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-6

---

*This check is added in this fork; not upstream. Maintained as part of
`mcp-verified` under MIT licence; see `LICENSE` and `checks/ATTRIBUTION.md`.*
