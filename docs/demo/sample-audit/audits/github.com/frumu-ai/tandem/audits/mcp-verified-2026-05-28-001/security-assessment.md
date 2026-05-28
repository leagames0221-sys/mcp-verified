# Security assessment

- **Target**: `https://github.com/frumu-ai/tandem`
- **Commit**: `050d7018f1a62a38d1b49c535561e8832142cf9d`
- **Audit id**: `mcp-verified-2026-05-28-001`
- **Auditor**: mcp-verified (leagames0221-sys)
- **Verdict**: **risky**
- **Status**: completed
- **Started**: 2026-05-28T18:51:20Z
- **Finished**: 2026-05-28T18:52:54Z
- **Time spent**: 1.57 min

## Findings summary

| Severity | Count |
|---|---|
| critical | 0 |
| high | 28 |
| medium | 0 |
| low | 0 |
| info | 0 |

## Findings

| Rule | Severity | Location | CWE |
|---|---|---|---|
| `EXEC-EXEC-CALL` | high | `apps/tandem-desktop/src-tauri/resources/packs/productivity-pack/dashboard.html:2541` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `apps/tandem-desktop/src-tauri/resources/skill-templates/algorithmic-art/templates/generator_template.js:133` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `apps/tandem-desktop/src-tauri/src/orchestrator/engine.rs:1336` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `apps/tandem-desktop/src/components/chat/Message.tsx:441` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `apps/tandem-desktop/src/components/files/FilePreview.tsx:333` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/book-a0b12cfe.js:88` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/elasticlunr-ef4e11c1.min.js:10` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/highlight-abc7f01d.js:6` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/mark-09e88c2c.min.js:7` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `guide/book/mark-09e88c2c.min.js:7` | CWE-95 |
| `EXEC-EXEC-CALL` | high | `scripts/extract-release-notes.js:124` | CWE-95 |

## Tools used

- `mcp-verified/0.0.1`
- `provider/mock`
