---
title: MCP Transport Layer Security Check
version: 1.0
date: 2026-05-29
tags: [security, MCP, transport, stdio, streamable-http, sse]
aliases: [mcp-transport, transport-security]
status: active
priority: high
cwe: [319, 295, 311]
cwe-primary: 319
vulnerability-db: []
---

# MCP Transport Layer Security Check

## Purpose

Identify server implementations whose MCP transport layer is misconfigured in ways that expose the agent-server channel to interception or tampering. This check is **added in this fork; not upstream** — it is modeled on §3 of arXiv:2510.16558.

## Why This Matters

MCP servers expose tools to AI agents over one of three transports: `stdio`, `streamable-http`, and `sse`. The HTTP-family transports terminate at a URL whose scheme determines whether the wire is encrypted. A server that advertises a `streamable-http` remote at an `http://` URL leaks every tool argument and every tool result over plaintext, including any credential the agent forwards as a tool input.

## For AI Assistants: Automated Analysis

Inspect:

- Server descriptors in `package.json`, `pyproject.toml`, or in the project's README that name a `remotes` array. For each `streamable-http` or `sse` entry, flag any URL whose scheme is not `https://`.
- Code paths that construct a transport endpoint dynamically. Flag any path where the scheme is derived from user input without validation.
- TLS certificate verification disabled in fetch / HTTP-client code: `verify=False`, `rejectUnauthorized: false`, `--insecure`, `requests.Session.verify = False`. These flags downgrade the channel even when the scheme is `https://`.

Severity guidance:

- `http://` transport on a server that authenticates the agent with a token → high.
- `verify=False` / `rejectUnauthorized: false` in a non-test code path → high.
- `http://` transport for a server that exposes only public, idempotent reads → medium.

## For Humans: Manual Assessment Steps

1. Read the project README's "transports" section. List every advertised endpoint URL and its scheme.
2. Grep the source for `verify=False`, `rejectUnauthorized: false`, `--insecure`, and the `NODE_TLS_REJECT_UNAUTHORIZED=0` environment variable.
3. For each finding, document whether the affected transport carries credentials or PII.

## Risk Evaluation

Plaintext transport defeats authentication: an attacker who can intercept the connection can replay the agent's token, observe tool arguments (which often include user secrets the agent is forwarding), and forge tool results that the agent will trust.

## Good and Bad Examples

```jsonc
// BAD: streamable-http over plaintext
"remotes": [
  { "type": "streamable-http", "url": "http://api.example.com/mcp" }
]

// GOOD: streamable-http over TLS
"remotes": [
  { "type": "streamable-http", "url": "https://api.example.com/mcp" }
]
```

```python
# BAD: TLS verification disabled
requests.post(url, json=payload, verify=False)

# GOOD: TLS verification enabled by default
requests.post(url, json=payload)
```
