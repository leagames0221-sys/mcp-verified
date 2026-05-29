---
title: Supply Chain Pre-Install Hook Detection
version: 1.0
date: 2026-05-29
tags: [security, MCP, supply-chain, npm, preinstall]
aliases: [preinstall-hook, install-hook, npm-lifecycle, shai-hulud]
status: active
priority: high
cwe: [506, 829, 494]
cwe-primary: 506
vulnerability-db: []
---

# Supply Chain Pre-Install Hook Detection

## Purpose

Surface MCP server packages whose `package.json` declares a
`preinstall`, `install`, or `prepare` script with network or shell
side effects. Such hooks fire **before** any application code runs
and, since the November 2025 Shai-Hulud worm variant, fire
**before** the historically-mitigating `--ignore-scripts` workflow
can intervene reliably.

This check is **added in this fork; not upstream** — it is grounded in
the deep-research probe of 2026-05-29 recorded under
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-2.
Primary evidence: Unit42's analysis of the Shai-Hulud worm's
November 2025 variant, which states that moving execution from
`postinstall` to `preinstall` "completely eliminates the need for human
interaction, guaranteeing execution on virtually every build server
processing the infected package."

## Why This Matters

Historically, security advice for npm-based MCP server installation
focused on `postinstall` scripts (the conventional install-time
exploit surface). The "do not run install scripts" guidance assumed
the attack happens after the package is on disk. The November 2025
variant of the Shai-Hulud worm invalidated that assumption by
pivoting to `preinstall`, which fires before npm even copies files
into `node_modules` on most workflows.

`mcp-verified` cannot prevent a user from running a malicious
package, but it can flag any registry entry whose npm lifecycle hooks
contain shell or network side effects so the user can decide before
the audit even completes whether the package is worth attempting.

## For AI Assistants: Automated Analysis

### Lifecycle Hook Inspection

```bash
# Locate all package.json files in the candidate tree
find . -name package.json -not -path '*/node_modules/*'

# Extract the lifecycle script entries
# Use jq if available, fall back to grep
for f in $(find . -name package.json -not -path '*/node_modules/*'); do
  echo "=== $f ==="
  jq -r '.scripts | to_entries[] | select(.key | test("^(preinstall|install|prepare|postinstall|preuninstall|postuninstall)$")) | "\(.key): \(.value)"' "$f" 2>/dev/null
done
```

### Suspicious Patterns Within Lifecycle Scripts

Red-flag tokens to grep for inside the script values above:

```text
curl | sh           # remote download piped to shell
wget | sh           # same, different fetcher
nc                  # netcat — outbound shell
base64 -d           # decoding before exec (obfuscation)
eval                # dynamic execution
node -e             # shell-exec flag (cross-ref with command-injection check)
python -c           # ditto
bash -c             # ditto
chmod +x            # making something executable just in time
process.env.NPM_TOKEN
$NPM_TOKEN          # token extraction (Shai-Hulud TTP)
postinstall_hooks.js
```

A script entry containing **any** of the above is a `critical` finding
even without further analysis — there is no legitimate reason for an
MCP server's install hook to download and execute remote code.

### Hash-Anchored Allowlist (Optional Enhancement)

For high-noise environments, maintain a hash-anchored allowlist of
known-benign install scripts (e.g. `node-gyp rebuild` and similar
build-time native-module compilation). A SHA-256 of the script value
matching the allowlist downgrades the severity to `informational`.

## For Humans: Manual Assessment Steps

1. **Open the candidate's `package.json`** and read each entry in
   `.scripts` that matches the lifecycle hook list above.
2. **For each non-empty hook**, ask: does this script perform any
   network call, shell exec, file write outside the package, or
   environment-variable read? If yes, flag.
3. **Read the candidate's README** for any mention of "post-install
   step required" — legitimate cases (downloading model weights,
   compiling native add-ons) should be documented. Undocumented
   install hooks with side effects are the higher-risk signal.
4. **Check the npm publish date vs. the GitHub last-commit date.** A
   package whose npm version is newer than its public GitHub HEAD
   is a Shai-Hulud / typosquat signal even before the install hook
   is inspected.

## Risk Evaluation

A `preinstall` or `install` hook with shell-exec or network side
effects is a **critical** finding. The Shai-Hulud worm demonstrated
that even brief execution windows on a build server suffice for npm
token theft and self-propagation. `mcp-verified`'s default `verified`
tier shall not apply to any candidate that ships such a hook unless
the hook is hash-anchored to a known-benign script.

A documented `postinstall` hook performing a build step (e.g.
`node-gyp rebuild`) is `informational`: less risk than `preinstall`
because some defensive workflows (`npm install --ignore-scripts`)
can suppress it. Severity may downgrade further if the hook script
is hash-anchored to a known-benign artifact.

## MCP-Protocol Category Mapping (per ADR-011)

`aliases: [supply-chain, preinstall-hook]` — touches the **Supply
Chain** category. Does not touch any protocol-semantic category;
this check is upstream of the MCP protocol entirely.

## Remediation Guidance

- Remove the `preinstall` and `install` hooks unless a legitimate
  build-time step requires them. Move build-time work to a separate
  documented script the user runs explicitly.
- If a hook is genuinely required, document its purpose in the README
  and confine its side effects to the package directory.
- For consumers: `npm install --ignore-scripts` is a partial
  mitigation for `postinstall` hooks but not for the Shai-Hulud
  November 2025 `preinstall` variant. The more durable mitigation is
  declining to install packages whose lifecycle hooks have
  unexplained network or shell side effects.

## References

- Unit42 — npm supply-chain attack analysis (Shai-Hulud Nov 2025):
  <https://unit42.paloaltonetworks.com/npm-supply-chain-attack/>
- ReversingLabs — Shai-Hulud worm timeline:
  <https://www.reversinglabs.com/blog/shai-hulud-worm-npm>
- Snyk — Postmark MCP empirical incident:
  <https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/>
- Project evidence file: `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-2

---

*This check is added in this fork; not upstream. Maintained as part of
`mcp-verified` under MIT licence; see `LICENSE` and `checks/ATTRIBUTION.md`.*
