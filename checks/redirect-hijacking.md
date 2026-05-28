---
title: MCP Redirect Hijacking
version: 1.0
date: 2026-05-29
tags: [security, MCP, redirect, ssrf, oauth, supply-chain]
aliases: [redirect-hijack, open-redirect]
status: active
priority: high
cwe: [601, 918, 346]
cwe-primary: 601
vulnerability-db: []
---

# MCP Redirect Hijacking

## Purpose

Identify MCP server implementations whose redirect-handling code can be hijacked to send authenticated requests to attacker-chosen hosts. This check is **added in this fork; not upstream** — it is modeled on the redirect-hijacking attack class identified in arXiv:2510.16558, where 304 of the surveyed MCP servers were found vulnerable.

## Why This Matters

When an MCP server's tool makes an outbound HTTP request, the HTTP client typically follows redirects. If the redirect target is not validated against an allowlist, an attacker who can influence the initial URL (directly via tool arguments or indirectly via a poisoned response) can pivot the request to a host of their choosing, carrying the server's credentials. The same gap also enables OAuth-flow hijacking: an OAuth provider's redirect URI parameter is occasionally trusted without strict host matching, letting an attacker walk away with the code grant.

## For AI Assistants: Automated Analysis

Inspect outbound HTTP code paths and flag:

- HTTP clients constructed with `allow_redirects=True` (the default in `requests` and `aiohttp`) where the input URL is user-influenced and no post-redirect host check is performed.
- Manual redirect-following loops (`while response.status_code in (301, 302, 303, 307, 308):`) that do not re-validate the `Location` header against the original host or an allowlist.
- OAuth code that compares the `redirect_uri` parameter against a list of allowed hosts using substring containment rather than exact host equality (e.g., `if "example.com" in redirect_uri:` instead of `if urlparse(redirect_uri).netloc == "example.com":`).
- SSRF-adjacent patterns: outbound URLs whose host segment comes from `request.json()`, `params`, or `kwargs` without canonicalization.

Severity guidance:

- An outbound HTTP path that follows redirects and forwards authentication headers cross-host → high.
- An OAuth flow that accepts a `redirect_uri` validated only by substring match → high.
- A read-only outbound path with no credentials that follows redirects without validation → medium.

## For Humans: Manual Assessment Steps

1. Map every outbound URL the server constructs from non-constant input.
2. For each, trace the HTTP-client configuration: are redirects followed? Are headers stripped on cross-host redirect? Is there a post-redirect host check?
3. If the server implements an OAuth flow, locate the redirect-URI comparison and confirm it uses exact host matching.

## Risk Evaluation

Redirect hijacking turns the MCP server into an unwitting proxy. Stolen credentials in this class of bug are often the server's own machine identity (a personal access token, a service account key), not the agent's — so the blast radius extends to every downstream service the server can reach.

## Good and Bad Examples

```python
# BAD: cross-host redirect followed silently with the bearer token attached
session = requests.Session()
session.headers["Authorization"] = f"Bearer {token}"
response = session.get(user_url, allow_redirects=True)

# GOOD: redirects disabled; outbound host validated against allowlist
allowed = {"api.example.com"}
parsed = urlparse(user_url)
if parsed.netloc not in allowed:
    raise ValueError(f"host not allowed: {parsed.netloc}")
response = requests.get(user_url, headers={"Authorization": f"Bearer {token}"}, allow_redirects=False)
```

```python
# BAD: OAuth redirect_uri trusted by substring containment
if "example.com" in redirect_uri:
    proceed()

# GOOD: OAuth redirect_uri validated by exact host equality
allowed_hosts = {"example.com", "auth.example.com"}
if urlparse(redirect_uri).netloc not in allowed_hosts:
    raise ValueError(f"redirect_uri not allowed: {redirect_uri}")
```
