---
title: Command Injection and Flag-Injection Bypass Detection
version: 1.0
date: 2026-05-29
tags: [security, MCP, command-injection, flag-injection, RCE]
aliases: [command-injection, flag-bypass, allowlist-bypass, stdio-rce]
status: active
priority: critical
cwe: [78, 77, 88, 94]
cwe-primary: 78
vulnerability-db: []
---

# Command Injection and Flag-Injection Bypass Detection

## Purpose

Surface two related failure-mode families that together account for the
single largest class of MCP-related CVEs in the 2025–2026 window:

1. **Direct command/subprocess injection** — `child_process.exec`,
   `execAsync`, `open()`, `spawn`, and `StdioServerParameters` invoked
   with template-string or string-concatenated user input that reaches
   a shell.
2. **Flag-injection bypass against command allowlists** — code that
   restricts the command name (e.g. only `npx`, `uvx`, `node`, `python`,
   `bash`) but does not restrict the **argument flags**, allowing an
   attacker-controlled `npx -c <cmd>`, `node -e <cmd>`, `python -c <cmd>`,
   or `bash -c <cmd>` to defeat the allowlist.

This check is **added in this fork; not upstream** — it is grounded in
the deep-research probe of 2026-05-29 recorded under
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`. Primary
evidence: `mcp-remote` CVE-2025-6514 (CVSS 9.6), `figma-developer-mcp`
CVE-2025-53967, `gemini-mcp-tool` CVE-2026-0755 (CVSS 9.8), Upsonic
CVE-2026-30625 and Flowise CVE-2026-40933 (the two flag-injection
bypass CVEs), plus the 12+ MCP-client RCE family enumerated by Ox
Security's MCP supply-chain advisory.

## Why This Matters

The audit literature documents that MCP servers and clients which
spawn external processes from user-influenced input form the
dominant CVE class for the protocol. The pattern is structurally
identical to classic OS command injection (CWE-78) but presents in
modern Python and Node code where developers reach for `exec` and
`open` as ergonomic conveniences rather than security-critical
sinks. The flag-injection variant is more recent and less widely
recognised: a developer who restricts the command to `npx`
("only-trusted-tool-runner") may still believe the allowlist is
sound when in fact `npx -c "$ATTACKER_PAYLOAD"` happily executes
arbitrary shell.

## For AI Assistants: Automated Analysis

### Critical Red Flags (Immediate Security Concerns)

```bash
# Python: subprocess invoked with shell=True and string input
grep -rEn "subprocess\.(call|check_call|check_output|run|Popen)\([^)]*shell\s*=\s*True" --include="*.py" .

# Python: os.system / os.popen on dynamic input
grep -rEn "os\.(system|popen)\(" --include="*.py" .

# Node/TS: child_process.exec / execAsync / execSync with template literals
grep -rEn "(child_process\.|cp\.)?(exec|execSync|execAsync|execFile)\(\s*\`[^\`]*\$\{" --include="*.js" --include="*.ts" --include="*.mjs" --include="*.cjs" .

# Node/TS: open() on user input (mcp-remote CVE-2025-6514 pattern)
grep -rEn "(^|\W)open\(\s*[^)]*req\.|^|\W)open\(\s*[^)]*ctx\." --include="*.js" --include="*.ts" .

# MCP Python SDK: StdioServerParameters where the command list element is computed at runtime
grep -rEn "StdioServerParameters\(" --include="*.py" -A 5 .
```

### Flag-Injection Bypass Patterns (Allowlist Defeats)

```bash
# Look for command allowlists that match only the binary name and
# pass through arguments verbatim
grep -rEn "(allowed_commands|allowlist|whitelist|safe_commands)\s*=\s*\[" --include="*.py" --include="*.js" --include="*.ts" -A 5 .

# Then look for the corresponding spawn site that does not also
# inspect the argument vector
grep -rEn "(spawn|exec)(File|Sync|Async)?\(\s*(allowedCommand|safeCommand|allowed_command|safe_command)" --include="*.js" --include="*.ts" --include="*.py" .

# Hard denylist for shell-exec flags — if any of these appear in the
# argv after an allowlisted command, the allowlist is bypassed
grep -rEn "['\"]?-c['\"]?\s*[+,]" --include="*.py" --include="*.js" --include="*.ts" .
grep -rEn "['\"]?-e['\"]?\s*[+,]" --include="*.js" --include="*.ts" .
```

### Positive Security Patterns

```bash
# subprocess.run with a list argv and shell=False (Python default-safe)
grep -rEn "subprocess\.run\(\s*\[" --include="*.py" .

# Node: execFile with array args and shell:false
grep -rEn "execFile\(\s*['\"][^'\"]+['\"]\s*,\s*\[" --include="*.js" --include="*.ts" .

# Explicit argv sanitisation / shlex.quote
grep -rEn "shlex\.(quote|join)" --include="*.py" .
```

## For Humans: Manual Assessment Steps

1. **Enumerate every shell-spawn sink in the candidate.** For each, ask
   whether any element of the command or argv can be influenced by an
   untrusted source (MCP request payload, environment variable, file
   contents from an untrusted path).
2. **If a command allowlist exists**, list its entries and check whether
   each binary on the allowlist has a shell-exec flag (`-c`, `-e`,
   `--command`, `--eval`). If yes, verify that the allowlist also
   restricts argument shape — not just the command name.
3. **Read the README / docs** for any "trusted runner" framing
   (e.g. "we only allow `npx`") and verify the implementation enforces
   the claim against flag injection, not just command-name injection.

## Risk Evaluation

A confirmed command-injection sink with reachable user input is a
**critical** finding — these CVEs have CVSS scores in the 9.x range
and routinely permit remote code execution. A flag-injection bypass
against a command allowlist is **critical** for the same reason: the
allowlist provides false assurance precisely because reviewers stop
reading once they see "we have an allowlist."

The lower-severity adjacency cases:

- **High**: a shell-spawn sink whose input is "almost" untrusted —
  e.g. a configuration file the server itself writes from MCP request
  data, then later spawns from. Two-hop reachability, same outcome.
- **Medium**: dynamic command construction with no current shell sink
  but where a future refactor could plausibly introduce one
  (the structural precondition without exploit reachability today).

## MCP-Protocol Category Mapping (per ADR-011)

`aliases: [command-injection, stdio-rce]` — touches the **Command
Injection** and **Protocol Violation** categories (the latter because
unsanitised `StdioServerParameters` violates the MCP spec's intent
that stdio commands be trusted operator input, not request-derived).

## Remediation Guidance

- Replace shell-spawn sinks with array-argv `execFile` (Node) or
  `subprocess.run([...], shell=False)` (Python).
- If a shell is genuinely required, route through `shlex.quote`
  (Python) or escape arguments per the target shell's quoting rules.
  Do not invent ad-hoc escapers.
- When implementing a command allowlist, validate the **whole argv
  shape** — command name, allowed flag set, allowed argument
  patterns — not just the command name. Reject `-c`, `-e`,
  `--command`, `--eval`, and any equivalent shell-exec flag on a hard
  denylist that runs before the allowlist check.
- Cite the CVEs in code comments at each sanitisation site so a future
  reviewer can verify the constraint is still being honoured.

## References

- CVE-2025-6514 (mcp-remote): <https://nvd.nist.gov/vuln/detail/CVE-2025-6514>
- CVE-2025-53967 (figma-developer-mcp): NVD listing
- CVE-2026-0755 (gemini-mcp-tool): NVD listing
- CVE-2026-30625 (Upsonic flag-injection bypass): NVD listing
- CVE-2026-40933 (Flowise flag-injection bypass): NVD listing
- Ox Security MCP supply-chain advisory: <https://www.ox.security/blog/mcp-supply-chain-advisory-rce-vulnerabilities-across-the-ai-ecosystem/>
- Project evidence file: `docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md` § F-1

---

*This check is added in this fork; not upstream. Maintained as part of
`mcp-verified` under MIT licence; see `LICENSE` and `checks/ATTRIBUTION.md`.*
