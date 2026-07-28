#!/usr/bin/env bash
# /wiki-doctor structural checks against a healthy (attached) install.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"
ADAPTER="$ROOT/adapters/claude-code"

# Attach a wiki (local create mode) so the structural checks have something real.
d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$ROOT/core/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )

out="$(cd "$d" && CLAUDE_PLUGIN_ROOT="$ADAPTER" bash "$ADAPTER/core/scripts/wiki-doctor.sh" 2>&1)"

assert_contains "$out" "plugin root resolves"          "check 1: plugin root"
assert_contains "$out" "gate files present"            "check 2: gates present"
assert_contains "$out" "sessionStart + postToolUse"    "check 3: hooks declared"
assert_contains "$out" "wiki attached at .llm-wiki/"   "check 4: wiki attached"
assert_contains "$out" "orientation dry-run emits"     "check 7: orientation dry-run"
assert_contains "$out" "structural failures: 0"        "no structural failures on a healthy install"

rm -rf "$d"

# Same structural checks against the Cursor adapter.
C="$ROOT/adapters/cursor"
d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$ROOT/core/init-wiki.sh" --agent cursor >/dev/null 2>&1 )

out="$(cd "$d" && CURSOR_PLUGIN_ROOT="$C" bash "$C/core/scripts/wiki-doctor.sh" 2>&1)"

assert_contains "$out" "plugin root resolves"          "cursor check 1: plugin root"
assert_contains "$out" "gate files present"            "cursor check 2: gates present"
assert_contains "$out" "sessionStart + postToolUse"    "cursor check 3: hooks declared"
assert_contains "$out" "wiki attached at .llm-wiki/"   "cursor check 4: wiki attached"
assert_contains "$out" "orientation dry-run emits"     "cursor check 7: orientation dry-run"
assert_contains "$out" "structural failures: 0"        "cursor: no structural failures on a healthy install"

rm -rf "$d"
exit "$ASSERT_FAIL"
