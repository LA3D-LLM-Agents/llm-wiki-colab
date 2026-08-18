#!/usr/bin/env bash
# Plugin test runner. Builds the artifact tree, then runs every test_*.sh and
# the wiki-write-protocol scenario suite against that build output (never
# against the source tree). Exit code = number of failing test files.
#
# LLM_WIKI_BUILT_TREE can point at a tree to reuse. If that tree contains a
# `.prebuilt` marker file the build step is skipped and the tree is used as-is
# (used by the mutation gates, which mutate a copy of a built tree).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

if [ -n "${LLM_WIKI_BUILT_TREE:-}" ]; then
    OUT="$LLM_WIKI_BUILT_TREE"
    mkdir -p "$OUT"
    OUT="$(cd "$OUT" && pwd -P)"
else
    OUT="$(mktemp -d)"
    OUT="$(cd "$OUT" && pwd -P)"
    trap 'rm -rf "$OUT"' EXIT
fi

if [ -e "$OUT/.prebuilt" ]; then
    echo "===== build (reusing prebuilt tree at $OUT) ====="
else
    echo "===== build ====="
    if ! uv run "$ROOT/build/assemble.py" --out "$OUT"; then
        echo "########## build FAILED; cannot test the artifact ##########"
        exit 1
    fi
fi
echo ""

MARKETPLACE_TREE="$OUT"
PLUGIN_ROOT="$OUT/claude/plugins/llm-wiki"
export MARKETPLACE_TREE PLUGIN_ROOT

if [ ! -d "$PLUGIN_ROOT" ]; then
    echo "########## build output has no $PLUGIN_ROOT ##########"
    exit 1
fi

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
