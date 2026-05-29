---
title: Tool-Schema Mutation Rug-Pull Detection (Static Precondition)
version: 1.0
date: 2026-05-29
tags: [security, MCP, rug-pull, tool-mutation, ETDI]
aliases: [rug-pull, schema-mutation, tool-definition-drift]
status: active
priority: high
cwe: [913, 506, 1357]
cwe-primary: 913
vulnerability-db: []
---

# Tool-Schema Mutation Rug-Pull Detection (Static Precondition)

## Purpose

Surface MCP servers whose source code constructs tool definitions
(`name`, `description`, `inputSchema`, `annotations`) from
runtime-mutable state. This is the **static precondition** for the
"rug-pull" attack class — a server that silently mutates a previously
approved tool definition to inject credential-exfiltration parameters
or coerce the consuming agent into new behaviour.

This check is **added in this fork; not upstream** — it implements the
static-fallback side of the dual-path detection strategy decided in
ADR-012. The dynamic side (live `tools/list` polling with SHA-256
schema-hash diff) is reserved for the future probe stage governed by
ADR-010 and is not shipped in Phase 1.

Primary evidence: arXiv preprint 2506.01333 (ETDI proposal) and the
Postmark MCP empirical incident (September 2025, npm
`postmark-mcp@1.0.16` exfiltrated emails via a silently-added BCC
header). Both are documented in
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-4.

## Why This Matters

MCP clients approve tool definitions once at session start and trust
them thereafter. There is no protocol-level mechanism that prevents
a server from returning a different tool definition on the next
`tools/list` call than it returned at approval time. The Postmark MCP
incident demonstrated that this is not a theoretical concern: a
single-line silent mutation of a published tool's behaviour exfiltrated
real customer data for weeks before discovery.

The full detection signal — schema-hash diff across observations —
requires connecting to the server and sampling its responses over
time, which Phase 1's read-only static path cannot legitimately do.
The static check instead detects the **structural precondition**:
a server whose source-level tool-definition construction code
depends on runtime-mutable state has the *capability* to rug-pull,
even if it does not exercise it today.

## For AI Assistants: Automated Analysis

### Tool-Definition Construction Site Inspection

```bash
# Python — common MCP server patterns
grep -rEn "(@mcp\.tool|@server\.tool|@app\.tool|Tool\(|register_tool)" \
  --include="*.py" -B 2 -A 15 .

# Node / TypeScript — common MCP server patterns
grep -rEn "(server\.setRequestHandler.*ListToolsRequestSchema|server\.tool\(|registerTool\()" \
  --include="*.js" --include="*.ts" -A 20 .
```

For each match, follow the tool-definition construction and ask:
does any of `name`, `description`, `inputSchema`, or `annotations`
derive from any of the following runtime-mutable sources?

```text
- Database query                    (e.g. async def get_tools(): rows = await db.execute(...))
- Network fetch                     (e.g. const desc = await fetch(remoteUrl).text())
- Environment variable read AFTER   (e.g. os.environ['DYNAMIC_DESC'] read inside handler)
  process start
- File read on a path the server    (e.g. open(self_writable_path).read())
  itself writes to
- Plugin / sub-process output       (e.g. tool desc piped from a helper binary)
```

If yes, emit a `rug-pull-precondition` finding. Severity guidance:

- **Critical**: the construction site derives the tool's
  `description` or `annotations` from a network fetch with no
  integrity verification — the simplest rug-pull payload site.
- **High**: derived from a database the server itself writes to
  (mutation can be triggered by the server's own MCP handlers).
- **Medium**: derived from environment variables read after process
  start (rotation of `env` between sessions is possible but rare).
- **Low**: derived from a local file the server reads at startup
  only (effectively static across the session, but flagged because
  a future code change could elevate the risk).

### Cross-Reference with Tool-Poisoning Check

If the same construction site is flagged by both this check and
`tool-poisoning-detection.md`, the combined verdict is **critical**:
mutable tool definitions whose content contains prompt-injection
markers are the literal Postmark MCP fingerprint.

## For Humans: Manual Assessment Steps

1. **List the tools the server exposes** by reading the
   tool-registration code (not by running the server).
2. **For each tool**, trace the construction of its `description` and
   `inputSchema` back to either (a) a literal string in source, or
   (b) one of the runtime-mutable sources above.
3. **Read the server's deployment story** — if the README instructs
   operators to set `TOOL_DESCRIPTIONS_URL` or similar to a remote
   endpoint, that is a `critical` finding because the rug-pull
   capability is the *intended* operating mode.
4. **Check version history** for any commit that changed a tool
   description or schema without bumping a SemVer minor or major.
   Silent schema-bumps are the same drift class even when committed
   in plain text.

## Risk Evaluation

This check produces only the **structural precondition** finding in
Phase 1. The check definition shall surface to the verdict
aggregator that "the static check detects the precondition;
observing actual mutation requires the dynamic-probe stage governed
by ADR-010, which Phase 1 does not yet ship."

This honest framing matters: a `rug-pull-precondition` finding does
not prove the server rug-pulls. It proves the server *can* rug-pull
without a code change. The verdict consequence is `caution` rather
than `risky` on its own; combined with a `tool-poisoning-detection`
hit or a credential-leak grep hit on the same tool's description,
the verdict elevates to `risky`.

When the dynamic probe stage lands (per ADR-012), the same check
name graduates to emit `rug-pull-precondition-only` (precondition
present but no mutation observed across N=3 samples) or
`rug-pull-mutation-observed` (precondition present and at least one
schema-hash diff disagreement). Consumers can track severity
progression by finding name without rewriting their aggregators.

## MCP-Protocol Category Mapping (per ADR-011)

`aliases: [rug-pull, tool-mutation]` — touches the **Rug-Pull** and
**Protocol Violation** categories (the latter because the MCP spec
implicitly assumes tool-definition constancy across a session).

## Remediation Guidance

- Construct tool definitions from literal source-code strings and
  pinned data files, not from runtime-mutable state.
- If dynamic tool registration is genuinely required (e.g. a server
  that adapts its tool set to which downstream service is
  configured), version each tool definition explicitly and surface
  the version in the tool's `annotations` so the consuming client
  can verify constancy.
- Implement integrity verification on any externally-fetched tool
  description (signed manifest, content-hash pin, attestation).
- For consumers: prefer MCP clients that implement the ETDI
  proposal (schema-hash diff per request) when it becomes
  available. Until then, periodically re-fetch and visually compare
  the tool definitions exposed by long-lived MCP servers.

## References

- arXiv 2506.01333 — Enhanced Tool Definition Interface (ETDI)
  proposal:
  <https://arxiv.org/html/2506.01333v1>
- Snyk — Postmark MCP empirical incident:
  <https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/>
- ADR-012 — Schema-hash diff as canonical rug-pull signal:
  `docs/adr/ADR-012-schema-hash-diff-for-rug-pull-detection.md`
- ADR-010 — Sandbox doctrine for future stdio probes:
  `docs/adr/ADR-010-sandbox-doctrine-for-future-stdio-probes.md`
- Project evidence file:
  `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-4

---

*This check is added in this fork; not upstream. Maintained as part of
`mcp-verified` under MIT licence; see `LICENSE` and `checks/ATTRIBUTION.md`.*
