# ADR-003 — Read-only static analysis, never execute candidate code

## Status

Accepted, 2026-05-28.

## Context

Auditing a candidate MCP server's source repository can use either:

- **Static analysis only**: clone the repo, parse files, run pattern matchers and AST analysis, ask an LLM to read selected files. Never invoke `npm install`, `pip install`, `node`, `python`, or any package-defined script.
- **Dynamic analysis**: install dependencies and run the server in a sandbox (Docker, nsjail, Firecracker). Trigger requests against the running server. Observe behavior.

Dynamic analysis catches more vulnerability classes (race conditions, runtime injection, real auth-gap exploitation), but requires significant sandbox infrastructure to do safely. A buggy or malicious candidate's `postinstall` script can ruin a developer machine; supply-chain attacks via npm have demonstrated this repeatedly (Shai-Hulud worm, the s1ngularity incident, the TeamPCP supply-chain compromise).

The Phase 1 strong-hire signal goal favors a tool that is **safe to run on a consumer laptop with no special setup**, even on first try, even against an unknown candidate.

## Decision

Phase 1 performs **read-only static analysis only**:

- `git clone --depth=1 --filter=tree:0 <repo> <scratch>` — shallow tree, no blob fetch beyond what is read.
- All check execution operates on file contents only.
- No `package.json` `scripts` invocation. No `setup.py` invocation. No `requirements.txt` install. No `Cargo.toml` build. No `go build`. No execution of any file inside the clone.
- The clone is removed at end-of-run or on per-candidate timeout.

If a check requires runtime evidence, it is out of scope for Phase 1; the check is either reformulated as a static heuristic with documented false-positive risk, or deferred.

## Consequences

**Positive**:

- A reviewer can `pip install mcp-verified` and run `mcp-verified audit --top 50` on any laptop with no fear of supply-chain compromise from candidates.
- The threat model for `mcp-verified` itself is much smaller — there is no sandbox to harden, no escape risk, no resource-exhaustion risk from candidates.
- Reproducibility is easier: static analysis output depends only on the candidate's commit hash and the auditor's check set, not on runtime state.

**Negative**:

- Some real vulnerabilities (race conditions, prompt-injection effects, network-side authn bypass) are out of reach for Phase 1 and are documented as such in `spec.md` § 5 out-of-scope.
- False-positive risk on static heuristics (e.g., "this server's auth check is suspicious") is higher than dynamic verification would give.

**Neutral**:

- Phase ≥ 2 may introduce optional sandboxed dynamic analysis behind an explicit opt-in flag; the Phase 1 module boundaries (`clone/`, `checks/runner.py`) accommodate that addition without rework.
