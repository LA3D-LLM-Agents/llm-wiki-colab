#!/usr/bin/env bash
# /wiki-doctor structural checks against a healthy (attached) install.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

# Attach a wiki (local create mode) so the structural checks have something real.
d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$PLUGIN_ROOT/core/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )

out="$(cd "$d" && CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$PLUGIN_ROOT/core/scripts/wiki-doctor.sh" 2>&1)"

assert_contains "$out" "plugin root resolves"          "check 1: plugin root"
assert_contains "$out" "gate files present"            "check 2: gates present"
assert_contains "$out" "SessionStart + PostToolUse"    "check 3: hooks declared"
assert_contains "$out" "wiki attached at .llm-wiki/"   "check 4: wiki attached"
assert_contains "$out" "orientation dry-run emits"     "check 7: orientation dry-run"
assert_contains "$out" "structural failures: 0"        "no structural failures on a healthy install"

rm -rf "$d"
exit "$ASSERT_FAIL"
