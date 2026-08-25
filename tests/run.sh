#!/usr/bin/env bash
# Plugin test runner. Builds the artifact tree, then runs every test_*.sh
# against that build output (never against the source tree).
# Exit code = number of failing test files.
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
    # Tests assert on tree shape, never on provenance, so the build gets fixed
    # values rather than reaching for a VCS. This keeps the suite runnable from
    # a secondary jj workspace that has no .git at all.
    if ! uv run "$ROOT/build/assemble.py" --out "$OUT" \
        --owner-repo "${LLM_WIKI_OWNER_REPO:-LA3D-LLM-Agents/llm-wiki-colab}" \
        --source-ref "${LLM_WIKI_SOURCE_REF:-0000000000000000000000000000000000000000}"; then
        echo "########## build FAILED; cannot test the artifact ##########"
        exit 1
    fi
fi
echo ""

MARKETPLACE_TREE="$OUT"
PLUGIN_ROOT="$OUT/claude/plugins/llm-wiki"
CODEX_PLUGIN_ROOT="$OUT/codex/plugins/llm-wiki"
CURSOR_PLUGIN_ROOT="$OUT/cursor/plugins/llm-wiki"
export MARKETPLACE_TREE PLUGIN_ROOT CODEX_PLUGIN_ROOT CURSOR_PLUGIN_ROOT

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

echo "########## failing test files: $FAIL ##########"
exit "$FAIL"
