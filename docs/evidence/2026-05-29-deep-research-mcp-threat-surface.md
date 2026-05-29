# 2026-05-29 — Deep-research probe of MCP threat surface for Top-50 audit design

> Evidence file capturing the structured output of a `/deep-research` dynamic-workflow
> run executed on 2026-05-29. Persisted per the project's primary-source-fetch
> retention practice so downstream ADRs (ADR-010, ADR-011, ADR-012) and check
> definitions can cite verified findings rather than re-fetching each time.

## Run metadata

| Field | Value |
|---|---|
| Date | 2026-05-29 |
| Tool | Claude Code dynamic workflows (research preview) — bundled `/deep-research` |
| Workflow run ID | `wf_ed2457ff-557` |
| Wall-clock | 9 min 5 s |
| Subagent count | 113 |
| Total output tokens | 5,428,885 |
| Tool calls | 399 |
| Phases | Scope (1) → Search (6 angles, parallel) → Fetch (30 sources) → Verify (25 claims × 3-vote adversarial) → Synthesize |

## Decomposition (6 search angles)

1. MCP-specific advisories & known vulns
2. Supply chain worm incidents (Shai-Hulud / s1ngularity)
3. Existing MCP audit tool findings
4. Over-broad permission / filesystem / SSRF in MCP servers
5. Credential leak & secrets in LLM tool ecosystems
6. Prompt injection vectors via MCP tool responses

## Confirmed findings (18 of 25 claims survived 2-of-3 adversarial verification)

The synthesis distilled the surviving claims into seven dominant failure-mode
families. Each is cited inline; full primary sources are listed in the
**Sources** section below.

### F-1 — Command/subprocess injection dominates the MCP CVE class

Unsanitized input passed to `child_process.exec` / `execAsync` / `open()` /
`StdioServerParameters` is the single largest MCP-related CVE class in the
2025-2026 window. Representative cases:

- `mcp-remote` versions 0.0.5–0.1.15: **CVE-2025-6514** (CVSS 9.6), `open()` shell sink.
- `figma-developer-mcp`: **CVE-2025-53967**, `child_process.exec` of `curl` argument.
- `gemini-mcp-tool`: **CVE-2026-0755** (CVSS 9.8), `execAsync` user input.
- 12+ additional MCP-client RCEs catalogued by Ox Security (LangFlow,
  GPT Researcher CVE-2025-65720, LiteLLM CVE-2026-30623, Agent Zero
  CVE-2026-30624, Bisheng CVE-2026-33224, Windsurf CVE-2026-30615, …).
- **Flag injection bypass**: simple command allowlists are defeated by
  `npx -c <cmd>` (Upsonic CVE-2026-30625, Flowise CVE-2026-40933). An
  allowlist that restricts the command name but not the arguments is not
  a defence.

**Static check signal**: grep for `child_process.exec` / `execAsync` / `open` /
`spawn` invoked with template-string or string-concatenated user input;
flag any STDIO command allowlist that does not also restrict flags.

### F-2 — Supply-chain attacks now include pre-install triggers and fake-contributor ecosystems

- **Shai-Hulud worm (November 2025 variant)** moved execution from `postinstall`
  to `preinstall`. Per Unit42: "completely eliminates the need for human
  interaction, guaranteeing execution on virtually every build server
  processing the infected package". The "no postinstall script" defence
  is no longer valid.
- The worm uses a stolen npm token to enumerate the maintainer's other
  packages via the `maintainer:` search filter and republishes them
  poisoned. Any MCP server npm package inherits supply-chain risk from
  every sibling package of its maintainer.
- **Postmark MCP** (npm `postmark-mcp` v1.0.16, September 2025): single-line
  BCC header to `phan@giftshop.club` exfiltrated 3000–15000 emails/day from
  ~300 orgs before npm takedown.
- **Oura MCP clone** (February 2026): SmartLoader gang built ≥5 AI-generated
  fake GitHub contributor profiles to manufacture credibility for a
  trojanised fork that delivered the StealC infostealer.

**Static check signal**: enumerate maintainer-graph blast radius (number of
sibling packages under the same npm maintainer), inspect `package.json` for
`preinstall` / `install` scripts, audit GitHub repo age + contributor profile
heuristics, surveil outbound network sinks (BCC headers, unexpected HTTP egress).

### F-3 — Credential-leak grep surface is well-defined

Per Unit42 (the exact harvest list Shai-Hulud targets) and OWASP MCP Top 10
(2025) MCP01 "Token Mismanagement and Secret Exposure":

- `.npmrc` files (npm tokens)
- GitHub Personal Access Tokens (PATs)
- AWS / GCP / Azure API keys
- SSH private keys
- **MCP debug log payloads** containing raw tokens passed in tool calls
  (OWASP MCP01 Scenario 2 "Log Scraping" — the MCP spec only uses
  SHOULD-level wording for sensitive-info redaction).

**Static check signal**: regex sweep for these credential shapes across
source + config + log paths; additionally flag MCP servers that log tool-call
arguments without an explicit redaction filter.

### F-4 — MCP-protocol-specific semantic threats

The `mcpserver-audit` README enumerates six expert-knowledge-area categories
(Prompt Injection, Confused Deputy, Token Theft, Data Exfiltration, Protocol
Violations, Cross-Origin Issues). `mcp-scan` (Invariant Labs) advertises
detection of Prompt Injection via tool descriptions, Tool Poisoning, Tool
Shadowing, and Toxic Flows enabling credential leakage — 15+ distinct risk
categories.

The **"rug pull"** class is formalised in arXiv preprint 2506.01333
(Bhatt / Narajala / Habler — Enhanced Tool Definition Interface proposal):
because MCP clients do not verify schema constancy across requests, a
server can silently mutate tool definitions post-approval to inject
credential-exfiltration parameters. **Postmark MCP** is the empirical
realisation.

> **Caveat (logged honestly)**: `mcpserver-audit` positions the six categories
> as "Expert Knowledge Areas" (educational taxonomy), not as a sealed check
> schema. The actual `/checks` directory does not 1:1 map to these six.
> Use as design taxonomy, not as a sealed test matrix — see ADR-011.

### F-5 — Network-exposure misconfigurations (0.0.0.0 bind, no auth)

- **CVE-2025-49596** (Anthropic MCP Inspector, patched v0.14.1 on
  2025-06-13, CVSS 9.4): default `0.0.0.0` bind + no auth on MCP Proxy
  stdio command endpoint + browser "0.0.0.0 Day" + DNS rebinding chain
  enabled zero-interaction RCE on dev machines just by visiting a
  malicious page while Inspector ran. Patch added session tokens,
  allowed-origin checks, and localhost-only bind — confirming both
  `0.0.0.0` bind AND missing auth are the inspectable failure modes.

**Static check signal**: scan server config/source for `0.0.0.0` / `*` bind,
missing auth middleware on HTTP/SSE transports, and absence of
Origin/Host validation.

### F-6 — Weak token lifecycle policy

OWASP MCP Top 10 (2025) MCP01 "How to Detect?" literally lists
"Token lifetimes are longer than session duration or lack enforced rotation"
as a detection criterion, and notes "MCP-based systems often operate
autonomously … a leaked token can grant high-impact permissions without
direct human intervention". Mitigation: "token renewal for every new MCP
session".

**Static check signal**: token TTL / rotation policy is typically declared
in config or manifest (`expires_in`, `max_age`, rotation policy field) and
amenable to grep-level static inspection.

> **Caveat (logged honestly)**: OWASP frames autonomy as a risk amplifier
> without literal comparison to traditional service accounts. Do not
> over-claim "disproportionately higher than service accounts" — keep
> wording at OWASP's level.

### F-7 — The audit harness itself is a security-sensitive component

`mcp-scan` README: "when Agent Scan scans an MCP configuration file, it
starts the stdio MCP servers by executing the commands and arguments
specified in the config" — and ships explicit consent prompts plus a
`--dangerously-run-mcp-servers` flag whose naming signals the danger.
The tool recommends Docker / VM / disposable env for untrusted configs.

Combined with the Ox-documented `npx -c <cmd>` whitelist bypass against
Upsonic / Flowise (F-1), this means a registry-wide MCP audit runner must:

1. Execute any audited server inside a disposable sandbox with no host
   credentials.
2. Treat the config-parse step itself as code execution.
3. If any allowlist is implemented, restrict argument flags, not just the
   command name.

This is **directly relevant** to `mcp-verified`'s `zero-credential` /
`local-first` design constraints. See ADR-010.

## Refuted claims (7 of 25 killed by 2-of-3 adversarial verification)

These claims did **not** survive verification and **must not** be cited by
`mcp-verified` design docs, the README, or marketing material.

| Claim | Vote | Source |
|---|---|---|
| 43% of tested MCP server implementations contained command injection flaws | 0–3 | Equixly blog (2025-03-29) |
| 22% of tested MCP servers permitted path traversal / arbitrary file read | 0–3 | Equixly blog (2025-03-29) |
| 30% of tested MCP servers permitted unrestricted URL fetching (SSRF) | 1–2 | Equixly blog (2025-03-29) |
| `mcpserver-audit` covers AI-specific failure modes beyond traditional static audit (prompt injection direct/indirect, model manipulation, training-data poisoning, output/context poisoning, model DoS, privacy extraction) — expanding the pilot's check surface beyond conventional credential/supply-chain checks | 0–3 | `mcpserver-audit` README |
| Indirect prompt injection through MCP tool responses is a distinct attack vector where adversaries inject malicious instructions via external data sources executed by agents, rather than via direct user input | 1–2 | arxiv 2602.07918 |
| Batched processing of requests obscures individual causal contributions, requiring retroactive chain-of-thought masking to recover attribution — a failure mode directly relevant to batched static audit designs | 0–3 | arxiv 2602.07918 |
| MCP STDIO transport is a systemic architectural flaw permitting subprocess execution without sanitization, affecting Flowise (CVE-2025-59528) and 150M+ downloads including LettaAI / LangFlow / Windsurf — auditors should flag STDIO servers that spawn `child_process` or expose `fs` modules | 0–3 | Authzed blog |

The most actionable refutation is the **Equixly prevalence trio**. These
numbers are widely cited in trade press but failed verification (single-blog
source, no published methodology or sample size). `mcp-verified` deliberately
does **not** cite them and instead intends the Top-50 pilot to be the first
defensible numerator / denominator measurement for these questions — see the
`README.md` "Limitations and honest framing" section.

## Open questions (registered for Phase 1.5 / Phase 2)

1. What is the empirically verified prevalence of command-injection /
   path-traversal / SSRF failures in the actual Top-50 popularity MCP
   servers? The Equixly figures are refuted, so the `mcp-verified` pilot
   may be the first credible measurement — design the pilot to publish
   defensible numerators and denominators.
2. Does the official MCP registry expose maintainer-graph metadata
   (sibling-package enumeration) sufficient to compute Shai-Hulud blast
   radius at scan time, or does `mcp-verified` need to mirror npm /
   GitHub maintainer APIs?
3. What is the canonical detection heuristic for "rug-pull" tool-definition
   mutation across sessions — schema hash diff per server per session?
   Is there prior-art tooling beyond the ETDI proposal, or is this a
   green-field check for `mcp-verified` to claim?
4. For LLM-assisted semantic vulnerability checks, what is the actual
   recall / precision delta between the Anthropic `security-guidance`
   plugin's `/security-review` and `mcp-scan` / `mcpserver-audit` on the
   same Top-50 corpus? (Relevant to the `session-eval` sibling project.)

## Sources (30 fetched, qualities tagged by the workflow)

| URL | Quality | Claims |
|---|---|---|
| <https://www.ox.security/blog/mcp-supply-chain-advisory-rce-vulnerabilities-across-the-ai-ecosystem/> | primary | 5 |
| <https://authzed.com/blog/timeline-mcp-breaches> | secondary | 5 |
| <https://nvd.nist.gov/vuln/detail/CVE-2025-6514> | primary | (cited) |
| <https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/> | primary | (cited) |
| <https://unit42.paloaltonetworks.com/npm-supply-chain-attack/> | primary | 5 |
| <https://www.reversinglabs.com/blog/shai-hulud-worm-npm> | secondary | 5 |
| <https://www.infoq.com/news/2025/10/npm-s1ngularity-shai-hulud/> | secondary | 5 |
| <https://snyk.io/blog/sha1-hulud-npm-supply-chain-incident/> | secondary | 5 |
| <https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/> | secondary | (cited) |
| <https://github.com/ModelContextProtocol-Security/mcpserver-audit> | primary | 4 |
| <https://github.com/invariantlabs-ai/mcp-scan> | primary | 4 |
| <https://pipelab.org/blog/state-of-mcp-security-2026/> | secondary | 5 |
| <https://agent-wars.com/news/2026-03-13-mcp-security-2026-30-cves-in-60-days-what-went-wrong> | secondary | 5 |
| <https://nvd.nist.gov/vuln/detail/CVE-2025-49596> | primary | (cited) |
| <https://owasp.org/www-project-mcp-top-10/2025/MCP01-2025-Token-Mismanagement-and-Secret-Exposure> | primary | 5 |
| <https://www.esentire.com/blog/model-context-protocol-security-critical-vulnerabilities-every-ciso-should-address-in-2025> | secondary | 5 |
| <https://arxiv.org/html/2506.01333v1> | primary | (cited) |
| <https://vulnerablemcp.info/taxonomy.html> | secondary | 5 |
| <https://www.endorlabs.com/learn/classic-vulnerabilities-meet-ai-infrastructure-why-mcp-needs-appsec> | secondary | 5 |
| <https://www.helpnetsecurity.com/2026/04/14/gitguardian-ai-agents-credentials-leak/> | secondary | 5 |
| Adversa, eSentire, dev.to, chatforest, Christian Schneider, Lakera, DataDome, StackOne, securityboulevard | blog / unreliable | varies |

## Verification posture

The dynamic workflow performed 3-vote adversarial verification on the 25
highest-confidence claims surfaced by the synthesis step. The verification
agents were prompted to **refute** by default (a higher bar than "confirm")
and a claim survived only when at least 2 of 3 verifiers failed to refute.
Seven claims were killed by this process and appear in the refuted-claims
table above. Token cost of the verification pass is included in the
5,428,885 total above; the cost is logged honestly so future budget planning
can use it as a calibration baseline rather than guessing.
