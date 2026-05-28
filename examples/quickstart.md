# Quickstart — five-command audit

This walkthrough takes a fresh clone of `mcp-verified` to a green audit run
in five commands. Total time should be **under 10 minutes on a 16 GB
consumer laptop**, including the first-time Python venv setup.

If a reviewer cannot reach this point from a fresh clone in 10 commands and
30 minutes, the project has failed the NFR-3 onboarding contract — please
open an issue.

## 0. Prerequisites

- Python 3.11 or 3.12.
- `git` on the PATH.
- Optional: an Ollama daemon if you want to exercise the LLM-assisted
  checks. The default `--provider mock` does not need Ollama.

## 1. Clone and install

```bash
git clone https://github.com/leagames0221-sys/mcp-verified
cd mcp-verified
python -m venv .venv
. .venv/Scripts/activate    # on Windows; use `.venv/bin/activate` on Linux / macOS
python -m pip install -e ".[dev]"
```

That installs the package in editable mode plus the dev dependencies
(`pytest`, `pytest-cov`, `ruff`, `pre-commit`). The runtime dependency
surface is the Python standard library only; no PyPI package is required
at runtime.

## 2. Sanity-check the install

```bash
mcp-verified version
```

Expected output (the exact version string may differ once tags land):

```
0.0.1
```

## 3. Walk the audit-help to see the available knobs

```bash
mcp-verified audit --help
```

The recorded version of this output is committed under
[`docs/demo/cli/audit-help.txt`](../docs/demo/cli/audit-help.txt).

## 4. Run an audit against the bundled registry fixture

```bash
mcp-verified audit \
    --fixture tests/fixtures/registry-snapshot-2026-05-28.json \
    --top 3 \
    --provider mock \
    --out my-audit
```

`--fixture` makes the run hermetic: no live registry call is issued, so
the command can run on an air-gapped laptop. Replace it with no
`--fixture` flag once you are ready to query the live registry.

Expected last line on stdout (depends on the fixture):

```
audited=3 verified=0 caution=0 risky=1 unknown=2 timeout=0 error=0
```

The summary fields are the seven AC-1.7 counters: `audited` is the total
number of candidates processed, and the four verdict buckets plus
`timeout` and `error` always sum to `audited`.

## 5. Browse the verdict registry

```bash
ls my-audit/audits/github.com/frumu-ai/tandem/audits/
cat my-audit/audits/github.com/frumu-ai/tandem/audits/*/security-assessment.md
```

The directory layout mirrors the upstream [Cloud Security Alliance
audit-db](https://github.com/ModelContextProtocol-Security/audit-db)
schema. A small canonical sample is committed under
[`docs/demo/sample-audit/`](../docs/demo/sample-audit/) so you can
compare layouts without running the audit.

## What to do next

- Run the test suite to confirm the install: `python -m pytest -q`.
- Run the local coverage gate: `python scripts/coverage_stdlib.py`.
- Read the design rationale in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
  and the nine ADRs under [`docs/adr/`](../docs/adr/).
- Try a real audit by dropping `--fixture` once your network can reach
  `https://registry.modelcontextprotocol.io/` and the candidate GitHub
  repositories.
