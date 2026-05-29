# ADR-010 — Sandbox doctrine for any future stdio-probe stage

## Status

Accepted, 2026-05-29.

## Context

Phase 1 deliberately never executes candidate code (ADR-003). All
analysis is performed on a shallow read-only `git clone --depth=1
--filter=tree:0` of the candidate's source tree, and AC-1.6 hard-aborts
the audit if any check tries to invoke `package.json`, `setup.py`, or
other installer-defined scripts.

A future phase may want to add a **dynamic-probe stage** that actually
spawns the candidate server's stdio process to capture its `tools/list`
response, observe runtime tool-definition mutation (the "rug-pull"
class — see ADR-012), or replay a benign payload to test network-bind
posture. As soon as such a stage exists, the audit harness itself
becomes the attacker's target: scanning a malicious MCP config will
literally execute the configured command. The `mcp-scan` project from
Invariant Labs documents this exact threat surface in its README, which
states "when Agent Scan scans an MCP configuration file, it starts the
stdio MCP servers by executing the commands and arguments specified in
the config" and ships an explicit `--dangerously-run-mcp-servers` flag
whose naming signals the risk.

The deep-research probe of 2026-05-29 (recorded in
`docs/evidence/2026-05-29-deep-research-mcp-threat-surface.md`) also
documents the **flag-injection bypass class** (CVE-2026-30625 against
Upsonic and CVE-2026-40933 against Flowise): a naive command allowlist
that restricts only the command name is defeated by passing
`npx -c <attacker-controlled-cmd>`, because the allowed `npx` is happy
to execute whatever `-c` argument it receives.

Phase 1 does not yet ship a dynamic probe and so does not yet inherit
these failure modes. But once such a stage is contemplated, the
constraints have to be in place before the first probe is written,
not after. This ADR records the doctrine so a future PR adding a
dynamic stage cannot land without satisfying it.

Options considered:

- **No-doctrine: rely on review at PR time.** Risk: an enthusiastic
  contributor lands a single-purpose probe behind a feature flag and
  the constraints get retrofitted later, by which time real candidates
  have run. Postmark MCP demonstrated that a single line of malicious
  code suffices for measurable harm in production; the audit harness
  is structurally a similar single line of trust.
- **Command-name allowlist only.** Insufficient per the
  CVE-2026-30625 / CVE-2026-40933 evidence — `npx -c` bypass.
- **Disposable sandbox + flag-level allowlist + explicit user opt-in.**
  Composable with the `mcp-scan` precedent. Cost is real but bounded:
  the sandbox is invoked only when the probe stage is invoked; static
  analysis (today's default path) is unaffected.

## Decision

Any future phase that adds a stage which executes a candidate's stdio
command shall, **before being merged to `main`**, satisfy all of the
following constraints. The release-gate script (`scripts/release_gate.sh`)
shall be amended at that time to verify each constraint mechanically.

1. **Disposable sandbox required.** Candidate stdio invocations shall run
   inside a single-use sandbox boundary (Docker container, Podman
   container, or Firejail / bubblewrap profile) that has no host
   credentials mounted, no host network namespace, and no writable
   bind-mount back to the host audit tree. The sandbox profile shall
   be declared in `docs/adr/` and pinned by digest, not by tag.

2. **Flag-level allowlist required.** If a candidate's stdio command is
   allowlisted by name (e.g. `npx`, `uvx`, `node`, `python`), the
   allowlist shall also restrict the **argument flags** permitted to
   each binary. `npx -c`, `node -e`, `python -c`, `bash -c`, and any
   equivalent shell-exec flag shall be on a hard denylist that the
   allowlist consults first. Flag-injection bypass against the
   allowlist shall be a release-gate failure, not a documentation note.

3. **Explicit user opt-in required.** The CLI subcommand that triggers
   the probe stage shall require an explicit `--dangerously-execute`
   flag (naming chosen to match the `mcp-scan` precedent so reviewers
   recognise the danger immediately). The default code path of every
   other subcommand shall continue to refuse stdio invocation entirely.

4. **Per-probe budget required.** Each candidate stdio invocation shall
   enforce a wall-clock budget (default 30 s) and a memory ceiling
   (default 512 MB) within the sandbox. Exceeding either causes the
   probe to terminate and emit a `probe-timeout` or `probe-oom` finding
   rather than crashing the run.

5. **Network egress denied by default.** The sandbox network profile
   shall block all outbound traffic except a documented allowlist
   (loopback only, by default). Any future probe that legitimately
   requires outbound traffic shall extend the allowlist via an ADR
   amendment, not a code-level override.

6. **Result laundering required.** Any output the probed server emits
   (stdout, stderr, JSON-RPC frames) shall pass through a redaction
   pass before being persisted in the verdict registry. Credential
   shapes (`sk-…`, `ghp_…`, `xoxb-…`, AWS-key patterns, `.npmrc` tokens)
   shall be redacted in the same form already used by the deterministic
   findings path (`sk-X…[REDACTED-N]`).

Phase 1 ships **no dynamic probe stage**. This ADR is the precondition
that any future PR adding one must satisfy. Until such a PR lands,
ADR-003 (read-only static analysis) governs the entire candidate-handling
surface.

## Consequences

**Positive**:

- The audit harness's own attack surface is bounded at the design level
  before any candidate code is ever executed. A future PR can implement
  the probe; it cannot quietly weaken the doctrine.
- The flag-level allowlist constraint is the lesson learned from real
  CVEs (CVE-2026-30625 / CVE-2026-40933), not an abstract worry. Naming
  the CVEs in the doctrine makes the reason auditable.
- The `--dangerously-execute` naming convention is borrowed from
  `mcp-scan`, which means a security reviewer familiar with the MCP
  audit ecosystem will recognise the shape of the opt-in without
  reading the project's docs first.
- Aligns with the project's `zero-credential` / `local-first` posture:
  even when the probe runs, it runs with no host credentials and no
  host network namespace.

**Negative**:

- The constraint set is non-trivial. A future PR adding a probe stage
  will be larger than a naïve "just spawn the command" implementation,
  and reviewer cost goes up accordingly. The trade-off is intentional:
  the cheap version is the one that gets exploited.
- Sandboxing on Windows is harder than on Linux. A probe stage that
  must run on the Windows CI matrix may need a `wsl2` indirection layer
  or be limited to Linux CI only. That decision belongs to the PR that
  introduces the stage, not to this ADR; calling it out here so the
  cost is visible early.
- `Docker` / `Podman` / `Firejail` add an install-time prerequisite
  that the static-analysis-only default path does not have. The CLI
  shall surface a clear error ("install Docker or omit `--dangerously-execute`")
  rather than silently degrading.

**Neutral**:

- This ADR adds no runtime dependency to Phase 1; it merely fences off
  the territory a future PR must respect.
- The doctrine is opinionated. A downstream user who wants a friendlier
  stdio probe (e.g. for trusted-internal MCP servers behind their own
  firewall) is free to fork; the constraint is for this project's
  default code path because this project audits the registry, and the
  registry contains untrusted code by definition.
