# Security policy

## Supported versions

`mcp-verified` is in early development. Only the `main` branch is supported. Pre-release tags do not receive security back-patches; upgrade to the latest `main` before reporting.

## Reporting a vulnerability

Open a private security advisory via the GitHub Security tab on this repository. Please include:

- Affected component (`mcp_verified/`, `checks/`, `scripts/`).
- Reproduction steps (commands, fixture, expected vs. actual).
- Suggested remediation if known.

Do not file public issues for security reports.

## Hardening posture

- **Untrusted code is never executed.** `mcp-verified` clones candidate server source as read-only and runs only static analysis. There is no `npm install` or `pip install` of candidate code.
- **No paid-API auto-call.** Cloud LLM providers (Anthropic, OpenAI, Gemini) are opt-in via explicit environment variables. The default code path talks only to `http://localhost:11434`.
- **Pre-commit chain.** `gitleaks` + path-leak guard + dependency-license audit run on every commit (`.pre-commit-config.yaml`).
- **Dependency license audit.** Only MIT / Apache 2.0 / BSD-2/3 / ISC licenses are permitted at runtime. The audit script (`scripts/audit_deps.py`) reads `pyproject.toml`, resolves each declared dependency's metadata, and exits non-zero on any disallowed or unknown license.
- **Dual-track documentation.** Repo-tracked files are public-safe. Local-only developer notes live outside the tracked tree and are explicitly blocked by `.gitignore`.

## Educational scope

Audit findings, threat model citations, and check templates may quote sanitized examples from public security research (e.g. arXiv 2510.16558, NSA CSI MCP Security). Quotation is for educational and defensive purposes and includes attribution per each source's license terms.
