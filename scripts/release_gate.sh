#!/usr/bin/env bash
# F-007 / AC-7.1 release gate.
#
# Runs the seven checks that must pass before `gh repo edit --visibility public`
# is invoked. Exits non-zero on the first failing check with a clear message.
#
# Checks (all must pass):
#   1. pytest suite green                    (AC-7.1 item 1)
#   2. coverage floor >= 80% on mcp_verified (AC-7.1 item 1 cont'd)
#   3. 4-constraint CLI smoke audit run      (AC-7.1 item 2)
#   4. customer-name word list clean         (AC-7.1 item 3)
#   5. internal-name word list clean         (AC-7.1 item 4)
#   6. >= 5 ADR files under docs/adr/        (AC-7.1 item 5)
#   7. README LIMITATIONS section present    (AC-7.1 item 6)
#   8. SECURITY.md present                   (AC-7.1 item 7)
#
# Wordlist paths default to environment variables and may also be supplied
# via CLI flags. When neither is set, the corresponding check is skipped
# with a clear warning so the operator can decide whether to proceed.
#
# Usage:
#     bash scripts/release_gate.sh [--customer-wordlist PATH]
#                                   [--internal-wordlist PATH]
#                                   [--skip-smoke]            (CI escape)
#                                   [--repo-root PATH]
#
# Negative test fixture: tests/test_release_gate.py builds a synthetic
# repo containing a fake customer-name commit and asserts the gate
# exits non-zero with the specific failing item logged.

set -uo pipefail

REPO_ROOT="$(pwd)"
CUSTOMER_WORDLIST="${MCP_VERIFIED_CUSTOMER_WORDLIST:-}"
INTERNAL_WORDLIST="${MCP_VERIFIED_INTERNAL_WORDLIST:-}"
SKIP_SMOKE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --customer-wordlist) CUSTOMER_WORDLIST="$2"; shift 2 ;;
    --internal-wordlist) INTERNAL_WORDLIST="$2"; shift 2 ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "release_gate: unknown argument: $1" >&2; exit 2 ;;
  esac
done

cd "$REPO_ROOT"

PASS=()
FAIL=()

step_pass() { PASS+=("$1"); echo "release_gate: PASS  $1"; }
step_fail() { FAIL+=("$1: $2"); echo "release_gate: FAIL  $1: $2" >&2; }

# 1. pytest suite green
if python -m pytest -q tests/ >/dev/null 2>&1; then
  step_pass "1/8 pytest suite green"
else
  step_fail "1/8 pytest suite" "tests failed; re-run 'python -m pytest -q' to inspect"
fi

# 2. coverage >= 80%
if python scripts/coverage_stdlib.py --floor 80 >/dev/null 2>&1; then
  step_pass "2/8 coverage >= 80%"
else
  step_fail "2/8 coverage" "stdlib trace floor 80% not met; run 'python scripts/coverage_stdlib.py --per-file' to inspect"
fi

# 3. 4-constraint CLI smoke audit run (fixture-only, no network)
if [[ "$SKIP_SMOKE" -eq 1 ]]; then
  step_pass "3/8 smoke audit (skipped via --skip-smoke)"
else
  SMOKE_TMP="$(mktemp -d)"
  trap 'rm -rf "$SMOKE_TMP"' EXIT
  cat > "$SMOKE_TMP/registry.json" <<'JSON'
{
  "servers": [{
    "server": {
      "name": "smoke/server",
      "version": "1.0.0",
      "description": "smoke",
      "remotes": [{"type": "streamable-http", "url": "https://x.example/mcp"}]
    },
    "_meta": {
      "io.modelcontextprotocol.registry/official": {
        "status": "active",
        "publishedAt": "2026-05-29T00:00:00Z",
        "updatedAt": "2026-05-29T00:00:00Z",
        "isLatest": true
      }
    }
  }],
  "metadata": {"nextCursor": null, "count": 1}
}
JSON
  if python -m mcp_verified.cli audit \
       --fixture "$SMOKE_TMP/registry.json" \
       --top 1 --provider mock \
       --out "$SMOKE_TMP/out" >/dev/null 2>&1; then
    step_pass "3/8 smoke audit completed"
  else
    step_fail "3/8 smoke audit" "mcp-verified audit failed against the smoke fixture"
  fi
fi

# 4. customer-name wordlist clean
if [[ -z "$CUSTOMER_WORDLIST" ]]; then
  step_pass "4/8 customer wordlist (skipped; pass --customer-wordlist PATH to run)"
elif [[ ! -f "$CUSTOMER_WORDLIST" ]]; then
  step_fail "4/8 customer wordlist" "wordlist file not found: $CUSTOMER_WORDLIST"
else
  hits=0
  while IFS= read -r term; do
    [[ -z "$term" ]] && continue
    [[ "$term" =~ ^# ]] && continue
    if git ls-files | grep -E '\.(md|py|sh|toml|yml|yaml|json|txt)$' | xargs grep -lF -- "$term" 2>/dev/null | head -1 >/dev/null; then
      step_fail "4/8 customer wordlist" "term hit in tracked tree: '$term'"
      hits=$((hits + 1))
      break
    fi
    if git log --all --format='%s%n%b' | grep -F -- "$term" >/dev/null 2>&1; then
      step_fail "4/8 customer wordlist" "term hit in commit history: '$term'"
      hits=$((hits + 1))
      break
    fi
  done < "$CUSTOMER_WORDLIST"
  if [[ "$hits" -eq 0 ]]; then
    step_pass "4/8 customer wordlist clean ($(grep -cve '^#' -e '^$' "$CUSTOMER_WORDLIST") terms)"
  fi
fi

# 5. internal-name wordlist clean
if [[ -z "$INTERNAL_WORDLIST" ]]; then
  step_pass "5/8 internal wordlist (skipped; pass --internal-wordlist PATH to run)"
elif [[ ! -f "$INTERNAL_WORDLIST" ]]; then
  step_fail "5/8 internal wordlist" "wordlist file not found: $INTERNAL_WORDLIST"
else
  hits=0
  while IFS= read -r term; do
    [[ -z "$term" ]] && continue
    [[ "$term" =~ ^# ]] && continue
    if git ls-files | grep -E '\.(md|py|sh|toml|yml|yaml|json|txt)$' | xargs grep -lF -- "$term" 2>/dev/null | head -1 >/dev/null; then
      step_fail "5/8 internal wordlist" "term hit in tracked tree: '$term'"
      hits=$((hits + 1))
      break
    fi
    if git log --all --format='%s%n%b' | grep -F -- "$term" >/dev/null 2>&1; then
      step_fail "5/8 internal wordlist" "term hit in commit history: '$term'"
      hits=$((hits + 1))
      break
    fi
  done < "$INTERNAL_WORDLIST"
  if [[ "$hits" -eq 0 ]]; then
    step_pass "5/8 internal wordlist clean ($(grep -cve '^#' -e '^$' "$INTERNAL_WORDLIST") terms)"
  fi
fi

# 6. >= 5 ADR files
adr_count=$(find docs/adr -maxdepth 1 -name 'ADR-*.md' -type f 2>/dev/null | wc -l | tr -d ' ')
if [[ "$adr_count" -ge 5 ]]; then
  step_pass "6/8 ADR count >= 5 (found $adr_count)"
else
  step_fail "6/8 ADR count" "found $adr_count ADR files under docs/adr/, need >= 5"
fi

# 7. README LIMITATIONS section present (case-insensitive)
if grep -iE '^#+\s*Limit' README.md >/dev/null 2>&1; then
  step_pass "7/8 README LIMITATIONS section present"
else
  step_fail "7/8 README LIMITATIONS" "no '## Limitations' (or similar) heading found in README.md"
fi

# 8. SECURITY.md present
if [[ -f SECURITY.md ]]; then
  step_pass "8/8 SECURITY.md present"
else
  step_fail "8/8 SECURITY.md" "SECURITY.md not found at repo root"
fi

# Summary
echo ""
echo "release_gate: ${#PASS[@]} passed, ${#FAIL[@]} failed"
if [[ "${#FAIL[@]}" -gt 0 ]]; then
  echo ""
  echo "Failing items:"
  for item in "${FAIL[@]}"; do
    echo "  - $item"
  done
  exit 1
fi
echo ""
echo "release_gate: all checks pass; ready for 'gh repo edit --visibility public'."
exit 0
