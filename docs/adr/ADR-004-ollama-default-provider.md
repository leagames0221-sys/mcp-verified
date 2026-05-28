# ADR-004 — Default LLM provider: Ollama `gemma3:4b`, temperature 0, structured output

## Status

Accepted, 2026-05-28.

## Context

Some checks (deep code review, prompt-style policy reasoning) benefit from LLM assistance. The four-constraint posture (free, no credit card, local-first, security-first) constrains the default provider:

- A reviewer must be able to run a full audit with no account and no paid key.
- The default must run on a 16 GB-RAM consumer laptop with ~8 GB available for the model.
- Reproducibility (AC-3.4) requires a setting choice that does not vary across two identical runs.

Available local options as of 2026-05:

- **Ollama** with various small open-weight models (`gemma3:4b`, `qwen2.5:7b`, `llama3.1:8b`, `mistral:7b`, `phi-3.5`).
- **llama.cpp** direct — lower-level, no HTTP server out of the box.
- **vLLM / Hugging Face TGI** — higher resource floors, not consumer-laptop default.

`gemma3:4b` has been used as the default in the sibling `mcp-guard` project; same default in `mcp-verified` keeps the cross-project "one local model serves the whole portfolio" story honest.

## Decision

Phase 1 default:

- Provider: **Ollama** at `http://localhost:11434`.
- Model: **`gemma3:4b`** (pinned in `pyproject.toml`).
- Temperature: **0**.
- Output: **structured JSON** matching a per-check schema. Non-JSON responses are rejected and the candidate is marked as `error`.
- Mock fallback (`providers/mock.py`): activated automatically when the provider is unreachable. Emits the empty-finding structured output and annotates `tools_used` with `mock-provider` so consumers can filter mock-derived verdicts. CI uses the mock by default.

Paid providers (Anthropic, OpenAI, Gemini) are present as `providers/<vendor>.py` modules but are refused at runtime unless `MCP_VERIFIED_PAID_PROVIDER_OPT_IN=1` is set explicitly, even when an API key is in the environment (AC-3.5).

## Consequences

**Positive**:

- Anyone with Ollama installed can reproduce a verdict.
- CI runs deterministically against the mock without ever calling out to a model.
- The four-constraint posture is enforceable at the provider boundary, not just stated in the README.

**Negative**:

- `gemma3:4b` is small; some nuanced checks may underperform what a paid 100B-class model could detect. Phase 1.5 probe B3 measures the gap between deterministic checks and LLM-assisted checks against a ground-truth set; if the gap is large, ADR-004 is revisited with a larger pinned model or a hybrid strategy.
- Temperature 0 does not fully guarantee determinism across different Ollama builds; the SHA-256 of the model file is recorded under `audit-manifest.json` `tools_used` for forensics.

**Neutral**:

- Switching the default model is a single-line `pyproject.toml` change plus an ADR amendment.
