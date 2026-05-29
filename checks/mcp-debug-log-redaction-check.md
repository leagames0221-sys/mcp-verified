---
title: MCP Debug Log Token-Redaction Inspection
version: 1.0
date: 2026-05-29
tags: [security, MCP, log-redaction, credential-leak, OWASP-MCP01]
aliases: [log-scraping, debug-log-leak, mcp-log-redaction]
status: active
priority: high
cwe: [532, 200, 312]
cwe-primary: 532
vulnerability-db: []
---

# MCP Debug Log Token-Redaction Inspection

## Purpose

Surface MCP servers whose debug or operational logging emits raw
request payloads, headers, or tool-call arguments without redacting
credential-shaped values. This is the **OWASP MCP Top 10 (2025)
MCP01 Scenario 2 "Log Scraping"** failure mode: any reader of the
server's log directory effectively gains read access to every token
that passed through the server.

This check is **added in this fork; not upstream**. The seed
`credential-management-security.md` (forked verbatim from upstream
under ADR-007) covers credential-storage anti-patterns but does not
inspect the orthogonal log-redaction failure mode. Grounded in
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-3.

## Why This Matters

MCP servers act as protocol bridges. They routinely log the JSON-RPC
frames they receive and send for debugging and operational
visibility. When those frames contain `Authorization` headers, OAuth
tokens, or API keys passed as tool arguments to downstream services,
the debug logs become a high-value exfiltration target. The MCP
specification only uses SHOULD-level wording for sensitive-info
redaction and its MUST scope is limited to log message format
(not to tool response bodies), so the protocol does not guarantee
protection here.

The Unit42 Shai-Hulud analysis explicitly names `.npmrc` tokens,
GitHub PATs, AWS / GCP / Azure keys, and SSH keys as the exact
harvest list that supply-chain attackers target. Debug logs that
contain any of these in unredacted form are immediately
weaponisable.

## For AI Assistants: Automated Analysis

### Identify Logging Sites That Touch Sensitive Payloads

```bash
# Python logging that emits request, payload, frame, headers, or tool args
grep -rEn "(logger|log|logging)\.(debug|info|trace|warning|error)\([^)]*(request|payload|frame|headers|tool_call|tool_args|message)" \
  --include="*.py" -B 1 -A 3 .

# Node / TypeScript console / pino / winston / bunyan equivalents
grep -rEn "(console\.(log|debug|info)|pino|winston|bunyan|log\.(debug|info|trace))\([^)]*(req|request|payload|frame|headers|toolCall|toolArgs|message)" \
  --include="*.js" --include="*.ts" --include="*.mjs" --include="*.cjs" -B 1 -A 3 .

# JSON-RPC frame logging — the dominant MCP-specific case
grep -rEn "(rpc|jsonrpc|json_rpc).*\.(debug|info|trace).*(frame|message|method|params)" \
  --include="*.py" --include="*.js" --include="*.ts" .
```

### Look for Redaction Filters

```bash
# Common Python redaction libraries / patterns
grep -rEn "(redact|mask_secrets|sanitize_log|filter_secrets|SecretsFilter|RedactingFilter|REDACT_PATTERN)" \
  --include="*.py" .

# Node redaction libraries / patterns
grep -rEn "(redact|maskSecrets|sanitizeLog|filterSecrets|pino-noir|redact-secrets)" \
  --include="*.js" --include="*.ts" .

# Explicit blocklists of header names that should never log
grep -rEn "(SENSITIVE_HEADERS|REDACTED_HEADERS|SECRET_KEYS)\s*=\s*[\[\{]" \
  --include="*.py" --include="*.js" --include="*.ts" .
```

### Search Committed Logs and Test Fixtures for Live Tokens

```bash
# Raw token shapes appearing in any committed log, snapshot, or fixture
grep -rEn "(sk-[a-zA-Z0-9]{32,}|xoxb-[0-9]+-[a-zA-Z0-9]+|ghp_[a-zA-Z0-9]{36}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._-]{20,})" \
  --include="*.log" --include="*.jsonl" --include="*.txt" --include="*.snap" \
  --include="*.fixture" --include="*.json" --include="*.yaml" --include="*.yml" .

# .npmrc tokens specifically (Shai-Hulud harvest target)
grep -rEn "_authToken\s*=\s*[A-Za-z0-9-_]{20,}" .
```

## Severity Bands

| Observation | Severity |
|---|---|
| Log site that emits raw request payload **and** no redaction filter visible anywhere in the module | high |
| Log site with partial redaction (some headers but not `Authorization` / `Cookie` / `X-Api-Key`) | medium |
| Log site with explicit redaction filter applied to every payload | informational |
| Live token shape found literally in a committed log fixture, snapshot, or `.npmrc` | critical |
| Logging level is `debug` or `trace` by default in production config | medium |

## For Humans: Manual Assessment Steps

1. **Locate the project's logging configuration** (e.g. `logging.yaml`,
   `pino.config.js`, the `logger` setup in `main.py`). Read the
   default log level and any redaction filter declarations.
2. **Open a representative request handler** that calls a downstream
   service with credentials. Trace from the credential read to every
   `logger.*` call inside the handler. Each call that includes the
   credential variable, the request body containing it, or the
   headers carrying it is a candidate finding.
3. **Open `tests/fixtures/` (or equivalent)**. Recorded transcripts of
   real MCP interactions are a frequent source of accidental live
   tokens. A token-shape grep over the fixture directory should
   return zero hits.
4. **Read `SECURITY.md` for the redaction policy.** Absence of any
   documented policy is an `informational` finding (the reader
   cannot know whether redaction is intentional or accidental).

## Risk Evaluation

Unredacted credential logging is the OWASP MCP01 Scenario 2 canonical
failure pattern. A `high` finding here combined with a `medium-high`
or `critical` finding from `supply-chain-maintainer-blast-radius-check`
elevates the verdict to `risky` — the combination is exactly the
threat model that Shai-Hulud exploits at scale.

The `critical` band — live tokens in a committed log fixture — is a
materialised incident, not a precondition. `mcp-verified` shall report
such findings even when the token has been revoked since publication
(it remains in history and on every consumer's clone).

## MCP-Protocol Category Mapping (per ADR-011)

`aliases: [credential-leak, log-scraping]` — touches the **Credential
Leak** and **Token Theft** categories.

## Remediation Guidance

- Apply a redaction filter at the **logging boundary**, not at
  individual call sites. A boundary filter cannot be forgotten by a
  new contributor adding a log line.
- Always redact `Authorization`, `Cookie`, `X-Api-Key`, `X-Auth-Token`,
  and any tool-argument field whose name matches the credential
  regex set used by `credential-management-security.md`.
- Mirror the redaction pattern `mcp-verified` itself uses
  (`sk-X…[REDACTED-N]`) so consumer-side log parsers can reliably
  detect redacted regions and statistics are recoverable.
- Default log level in production should be `info` or `warning`;
  `debug` and `trace` belong behind an explicit operator opt-in.
- Never commit debug log fixtures containing literal tokens; use
  synthetic placeholders in test data.

## References

- OWASP MCP Top 10 (2025) MCP01 — Token Mismanagement and Secret
  Exposure (Scenario 2 "Log Scraping"):
  <https://owasp.org/www-project-mcp-top-10/2025/MCP01-2025-Token-Mismanagement-and-Secret-Exposure>
- Unit42 — npm supply-chain attack (Shai-Hulud harvest list):
  <https://unit42.paloaltonetworks.com/npm-supply-chain-attack/>
- Project evidence file:
  `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-3
- Companion check (storage anti-patterns; forked verbatim from
  upstream): `checks/credential-management-security.md`

---

*This check is added in this fork; not upstream. Maintained as part of
`mcp-verified` under MIT licence; see `LICENSE` and `checks/ATTRIBUTION.md`.*
