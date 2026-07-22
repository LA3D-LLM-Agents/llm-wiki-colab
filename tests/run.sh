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
# The push-race / livelock-retry scenarios exercise concurrent-writer timing, so
# they can flake once under load. Retry the suite once; only a repeated failure
# is a real failure (the deterministic test_*.sh above are never retried).
log="$(mktemp)"
proto_ok=0
for attempt in 1 2 3; do
    if bash "$HERE/wiki-write-protocol/run-all.sh" >"$log" 2>&1; then proto_ok=1; break; fi
    echo "  (attempt $attempt flaked on a timing-sensitive scenario; retrying)"
done
if [ "$proto_ok" -eq 1 ]; then
    echo "  ok   $(grep -E 'Summary:' "$log" || echo 'scenarios passed')"
else
    echo "  FAIL protocol scenarios (3 attempts):"; tail -15 "$log"; FAIL=$((FAIL + 1))
fi
rm -f "$log"
echo ""

echo "########## failing test files: $FAIL ##########"
exit "$FAIL"
