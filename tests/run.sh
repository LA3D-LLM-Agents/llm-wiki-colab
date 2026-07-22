#!/usr/bin/env bash
# Plugin test runner. Assembles the adapter (copies core/ in), runs every
# test_*.sh, then the wiki-write-protocol scenario suite. Exit code = number of
# failing test files.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# Assemble core into the adapter so ${CLAUDE_PLUGIN_ROOT}/core/... resolves.
bash "$ROOT/adapters/claude-code/package.sh" >/dev/null

FAIL=0
for t in "$HERE"/test_*.sh; do
    echo "===== $(basename "$t") ====="
    if bash "$t"; then :; else FAIL=$((FAIL + 1)); fi
    echo ""
done

echo "===== wiki-write-protocol scenarios ====="
log="$(mktemp)"
if bash "$HERE/wiki-write-protocol/run-all.sh" >"$log" 2>&1; then
    echo "  ok   $(grep -E 'Summary:' "$log" || echo 'scenarios passed')"
else
    echo "  FAIL protocol scenarios:"; tail -15 "$log"; FAIL=$((FAIL + 1))
fi
rm -f "$log"
echo ""

echo "########## failing test files: $FAIL ##########"
exit "$FAIL"
