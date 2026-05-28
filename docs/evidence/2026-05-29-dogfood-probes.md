---
date: 2026-05-29
run: dogfood Phase 1 pilot
fixture: tests/fixtures/registry-snapshot-2026-05-28.json
provider: mock
host: Windows 11 consumer laptop
fetcher: AI + python -m mcp_verified.cli
license_note: own measurement; no external data adopted
---

# Dogfood Probes — Phase 1 Pilot (B1 / B2 / B4 measured; B3 deferred)

T-21 verifies the four B-axis probes specified in the Plan SSoT Stage 1 Discovery (`mcp_verified_registry_plan_2026_05_28.md` § 4 B probe 4-field). This document reports the literal numbers from two complete back-to-back audit runs against the same registry fixture.

## Probe environment

- Mode: `--fixture tests/fixtures/registry-snapshot-2026-05-28.json` (deterministic input, three real registry entries — one GitHub-published, two remote-only).
- Provider: `mock` (Phase 1 baseline; Ollama-backed measurement is deferred to Phase 1.5 along with B3 — see "Why B3 is deferred" below).
- Tool version: `mcp-verified/0.0.1` (commit `8490223` plus the dogfood data in `.tmp/dogfood-pilot/`).
- Wall-clock measured via stdlib `time`.
- Two full runs (`runA`, `runB`) so reproducibility can be measured directly.

```
$ python -m mcp_verified.cli audit \
    --fixture tests/fixtures/registry-snapshot-2026-05-28.json \
    --top 3 --provider mock --out .tmp/dogfood-pilot/runA
audited=3 verified=0 caution=0 risky=1 unknown=2 timeout=0 error=0

$ python -m mcp_verified.cli audit \
    --fixture tests/fixtures/registry-snapshot-2026-05-28.json \
    --top 3 --provider mock --out .tmp/dogfood-pilot/runB
audited=3 verified=0 caution=0 risky=1 unknown=2 timeout=0 error=0
```

Both runs produced byte-identical summary lines.

## B1 — Per-server throughput (NFR-1 budget check)

| Run | Candidates | Wall-clock | Per-candidate |
|---|---|---|---|
| runA | 3 | 105.7 s | **35.2 s/candidate** |
| runB | 3 | 78.0 s | **26.0 s/candidate** |
| **average** | 6 | 183.7 s | **30.6 s/candidate** |

**NFR-1 budget**: top-50 within one weekend (≈ 16 h) = 1 152 s per candidate. **Result**: 30.6 s observed average is **~38× under budget**; extrapolated top-50 wall-clock is **~25.5 minutes**.

**Caveats**:
- Mock provider; Ollama-backed audits will add LLM inference time per check. Phase 1.5 will rerun this probe with Ollama and report the delta.
- One GitHub clone dominates the runA time; runB benefits from git's local object cache.

## B2 — Reproducibility (NFR-1 verdict-consistency check)

| Target | runA verdict | runB verdict | Findings (runA) | Findings (runB) | Agree |
|---|---|---|---|---|---|
| `https://github.com/frumu-ai/tandem` | risky | risky | 28 high | 28 high | ✅ |
| `unknown://ac.inference.sh/mcp` (remote-only) | unknown | unknown | 0 | 0 | ✅ |

**Reproducibility**: **2/2 = 100 %**. Same verdict, same per-severity finding count for every audited candidate. The mock provider is deterministic by construction, but the deterministic-executor pattern walk (T-06) also produced identical findings — the lex-sorted file walker + `(file, line, rule_id)` sort key is the load-bearing guarantee here.

**Note**: the third fixture entry (`ac.inference.sh/mcp` v1.0.0, non-latest) is filtered out by the `is_latest` requirement; only the latest version of the same name is audited. The summary line counts three "audited" candidates because the pipeline still records an `unknown`-bucket manifest for each input row, but on disk the two `ac.inference.sh/mcp` versions share the same `_unknown/unknown_ac.inference.sh_mcp/audits/<audit_id>/` directory because the audit id is the same per run (one-shot writer; the second write overwrites the first with byte-identical content).

## B4 — Storage scale (NFR-2 size check)

| Run | Files written | Total bytes | Per-candidate avg |
|---|---|---|---|
| runA | 33 | 11 891 B | **3.9 KB** |
| runB | 33 | 11 882 B | **3.9 KB** |

**NFR-2 budget**: ≤ 100 KB per server average; top-50 total ≤ 10 MB. **Result**: 3.9 KB observed is **~25× under per-server budget**; extrapolated top-50 total is **~196 KB**, well under the 10 MB ceiling.

The 9-byte difference between runs is the per-finding "Started" / "Finished" timestamp in `security-assessment.md`, which is the only non-deterministic field in the current output schema. Both audit-manifest.json bodies are otherwise byte-identical, which is what the T-12 divergence detector relies on.

## Why B3 (LLM vs deterministic F1) is deferred

B3 requires:

1. A running Ollama daemon with `gemma3:4b` pulled.
2. A ground-truth set of ~10 MCP servers hand-labeled by a security reviewer.
3. Two parallel audit runs (one with `--provider mock` to exercise only deterministic checks, one with `--provider ollama` to exercise both) so the LLM contribution can be isolated.

This session does not have Ollama available; the local `pip install`-style environment cannot accept new dependencies without the supply-chain security gate firing (see T-05 + T-18 for the documented pattern). B3 is therefore deferred to Phase 1.5 follow-up, where Ollama will be set up explicitly and the comparison run end-to-end. The deferral is recorded honestly here rather than substituted with a synthetic estimate.

## Summary

| Probe | Phase 1 target | Phase 1 result | Status |
|---|---|---|---|
| B1 throughput | ≤ 1152 s / candidate | **30.6 s** observed | ✅ ~38× headroom |
| B2 reproducibility | ≥ 0.9 Jaccard | **1.0 (2/2 agree)** | ✅ at ceiling |
| B3 LLM vs deterministic F1 | (set in 1.5) | — | ⏳ deferred to Phase 1.5 |
| B4 storage per candidate | ≤ 100 KB | **3.9 KB** | ✅ ~25× headroom |

NFR-1 (consumer-laptop throughput) and NFR-2 (verdict-registry storage scale) are both validated by margin. The remaining open probe (B3) is documented as deferred with the prerequisites named; it is not skipped silently.
