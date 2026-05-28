# Attribution

The check definitions in this directory are seeded from the upstream
[`mcpserver-audit`](https://github.com/ModelContextProtocol-Security/mcpserver-audit)
project (a Cloud Security Alliance community project, Apache-2.0).
This document records the seed origin so reviewers and downstream
consumers can trace each check file back to its upstream version.

## Upstream snapshot

- **Repository**: <https://github.com/ModelContextProtocol-Security/mcpserver-audit>
- **License**: Apache License, Version 2.0
- **Commit pinned**: `8e54ffb77e710bd26009786d93a5df154fa4b45d`
- **Fork date**: 2026-05-29

## Files forked verbatim

The following files were fetched from the upstream `checks/` directory
at the pinned commit and are mirrored here without content modification:

| File | Upstream status | Notes |
|---|---|---|
| `credential-management-security.md` | `active` | CWE-798, 200, 522. |
| `advanced-obfuscation-evasion-security-check.md` | `active` | CWE-506, 656, 546, 676. |
| `dynamic-content-execution-security-check.md` | `active` | CWE-94, 829, 494, 349. |
| `python-authentication-semgrep-security-check.md` | `active` | CWE-798, 327, 256, 862, 319, 532, 614, 338, 89. |
| `ci-secrets.md` | `draft` | CWE-798, 522, 532, 16. Skipped at load time (status != active). |
| `http-client-resilience.md` | `draft` | CWE-400, 703, 307. Skipped at load time. |

The two `draft` files are retained as-is so a reviewer can see the
upstream state; the loader (`mcp_verified.checks.loader`) honors the
upstream convention that `status != "active"` files are excluded from
the audit set.

## Files excluded from the fork

- `README.md`, `CHECK-TEMPLATE.md`, `README-python-authentication-semgrep-security-check.md`, `main-prompt.md` — companion documentation that is not itself a check.
- `docker-security.md`, `compose-security.md`, `k8s-security.md` — out of scope for the Phase 1 MCP-server source audit threat model.
- `network-port-binding-security-check.md` — the upstream file lacks the YAML frontmatter envelope our loader requires; we did not modify upstream content to make it parseable, so the file is excluded rather than edited.

## Files added in this fork (not from upstream)

These checks are MCP-specific extensions modeled on the attack
taxonomy in Wang et al., "A First Look at the Security Issues in the
Model Context Protocol Ecosystem" (arXiv:2510.16558, accepted to
DSN 2026). They follow the upstream's five-section structure but are
original content:

- `mcp-transport-security.md` — transport-layer concerns specific to MCP (stdio / streamable-http / SSE).
- `tool-poisoning-detection.md` — adversarial tool-definition surfaces unique to the protocol.
- `redirect-hijacking.md` — the redirect-hijacking class identified in the arXiv paper (304 servers found vulnerable across the studied registries).

Each MCP-specific check file declares its own `aliases` block pointing to the arXiv paper and notes "added in this fork; not upstream" in its `## Purpose` section.

## License terms preserved

Per the Apache License, Version 2.0 §4, this attribution document
preserves:

- The copyright notice of the upstream project.
- A "NOTICE" reference: this repository is a derivative work; the
  forked files retain the upstream Apache 2.0 license. Downstream
  consumers redistributing this repository's `checks/` content must
  preserve this attribution.

The mcp-verified project itself is MIT-licensed (see `../LICENSE`);
the MIT and Apache 2.0 licenses are compatible, so this repository
can ship MIT-licensed code that consumes Apache 2.0-licensed check
definitions without any license conflict.

## How to refresh

To bump the pinned upstream commit:

1. Inspect the upstream `checks/` diff between the current pin and the
   target commit.
2. Re-curl each file in the "forked verbatim" table from the new
   commit's raw URL.
3. Run `python -m pytest tests/test_checks_directory.py` to confirm
   the loader still parses every active file cleanly.
4. Update the **Commit pinned** and **Fork date** lines above.
5. If any newly-introduced upstream check requires loader-grammar
   extensions, raise the question in an ADR amendment rather than
   silently broadening the parser.
