#!/usr/bin/env bash
# Private path / internal-name leak guard (Layer 2 + Layer 4).
#
# Blocks any tracked file from containing:
#   * Absolute Windows user paths (C:\Users\...)
#   * Internal local-config directory references
#   * Internal infrastructure abstractions (developer-only names)
#
# Runs on pre-commit and as a manual sweep before pushing to a public remote.
# The patterns are built from string fragments at runtime so this script's
# own source does not contain the literal patterns it scans for.
#
# Exit codes:
#   0 - clean
#   1 - one or more patterns matched

set -euo pipefail

# Build patterns from fragments so this script's source does not match itself.
DOTSEG=".""cla""ude"

PATTERNS=(
  'C:\\Users\\'
  "/\\${DOTSEG}/"
  "~/\\${DOTSEG}"
  '\bknowledge-''library\b'
  '\bsecretary_''triage\b'
  '\bPJ_''REGISTRY\b'
)

# Files to scan: all git-tracked files except this script and the pre-commit
# config (both intentionally reference the patterns they enforce).
mapfile -t FILES < <(git ls-files \
  | grep -v \
    -e '^scripts/private_path_check\.sh$' \
    -e '^\.pre-commit-config\.yaml$' \
  || true)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "private_path_check: no files to scan"
  exit 0
fi

HITS=0
for pattern in "${PATTERNS[@]}"; do
  if matches=$(grep -nE "$pattern" "${FILES[@]}" 2>/dev/null); then
    echo "private_path_check: pattern matched:" >&2
    echo "$matches" >&2
    HITS=$((HITS + 1))
  fi
done

if [[ $HITS -gt 0 ]]; then
  echo "" >&2
  echo "private_path_check: ${HITS} pattern(s) matched. Commit blocked." >&2
  echo "Remove the leaking content, or add a justified exception above." >&2
  exit 1
fi

echo "private_path_check: clean (${#FILES[@]} files scanned, 0 hits)"
exit 0
