#!/usr/bin/env bash
# /wiki-doctor structural checks against a healthy (attached) install, in every
# harness dialect. One byte-identical script ships into all three subtrees, so
# it has to read the tree it was copied into rather than assume Claude's shape.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT CODEX_PLUGIN_ROOT

# Attach a wiki (local create mode) so the structural checks have something real.
d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$PLUGIN_ROOT/core/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )

run_doctor() {
    ( cd "$d" && CLAUDE_PLUGIN_ROOT="$1" bash "$1/core/scripts/wiki-doctor.sh" 2>&1 )
}

# --- Claude subtree --------------------------------------------------------
out="$(run_doctor "$PLUGIN_ROOT")"

assert_contains "$out" "plugin root resolves"          "check 1: plugin root"
assert_contains "$out" "claude dialect"                "check 1: claude dialect detected"
assert_contains "$out" "gate files present"            "check 2: gates present"
assert_contains "$out" "SessionStart + PostToolUse"    "check 3: hooks declared"
assert_contains "$out" "wiki attached at .llm-wiki/"   "check 4: wiki attached"
assert_contains "$out" "orientation dry-run emits"     "check 7: orientation dry-run"
assert_contains "$out" "structural failures: 0"        "no structural failures on a healthy install"

# --- Codex subtree ---------------------------------------------------------
# The real emitted tree, not a fixture: it carries .codex-plugin/ and no
# .claude-plugin/ at all, which is the case the manifest check used to fail.
cout="$(run_doctor "$CODEX_PLUGIN_ROOT")"

assert_contains "$cout" "codex dialect"                "codex: dialect detected from .codex-plugin/"
assert_contains "$cout" "SessionStart + PostToolUse"   "codex: Claude-dialect hook names still expected"
assert_contains "$cout" "orientation dry-run emits"    "codex: orientation dry-run"
assert_contains "$cout" "structural failures: 0"       "codex: no structural failures"

# --- Cursor dialect --------------------------------------------------------
# A shaped fixture, not the emitted tree: the Cursor emitter does not exist yet
# at this phase. It exercises the branch selection only (which manifest names
# the dialect, which hook key is demanded, which entry point the dry-run calls);
# test_cursor_manifests.sh runs the same script against the real subtree.
cur="$(mktemp -d)" && cur="$(cd "$cur" && pwd -P)"
cp -R "$PLUGIN_ROOT/." "$cur/"
rm -rf "$cur/.claude-plugin"
mkdir -p "$cur/.cursor-plugin"
printf '{"name":"llm-wiki","version":"0.0.0"}\n' >"$cur/.cursor-plugin/plugin.json"
printf '{"version":1,"hooks":{"sessionStart":[{"type":"command","command":"bash cursor-session-start.sh"}]}}\n' \
    >"$cur/hooks/hooks.json"
cat >"$cur/hooks/cursor-session-start.sh" <<'WRAPPER'
#!/usr/bin/env bash
exec bash "$1/hooks/session-start.sh"
WRAPPER
chmod 0755 "$cur/hooks/cursor-session-start.sh"

ucout="$(run_doctor "$cur")"

assert_contains "$ucout" "cursor dialect"              "cursor: dialect detected from .cursor-plugin/"
assert_contains "$ucout" "hooks.json declares sessionStart" \
    "cursor: lowercase sessionStart satisfies the hook check"
assert_not_contains "$ucout" "SessionStart + PostToolUse" \
    "cursor: no PostToolUse advisory demanded"
assert_contains "$ucout" "orientation dry-run emits"   "cursor: dry-run runs through the adapter"
assert_contains "$ucout" "structural failures: 0"      "cursor: no structural failures"

# The cursor branch must still be able to fail: drop the adapter the wrapper
# check names and the dry-run has to report a structural failure, not pass by
# silently falling back to the Claude entry point that is still present.
rm -f "$cur/hooks/cursor-session-start.sh"
bcout="$(run_doctor "$cur")"
assert_contains "$bcout" "hooks/cursor-session-start.sh missing" \
    "cursor: a missing adapter is reported"
assert_not_contains "$bcout" "structural failures: 0" \
    "cursor: a missing adapter is a structural failure"

# --- no plugin-root variable in the environment ----------------------------
# The Cursor case in the field: sessionStart's `env` output reaches later hook
# executions but not the shell the agent runs a skill's commands in, so the
# script is invoked by absolute path with nothing exported. It has to locate
# itself rather than report a broken install.
nout="$( cd "$d" && env -u CLAUDE_PLUGIN_ROOT bash "$PLUGIN_ROOT/core/scripts/wiki-doctor.sh" 2>&1 )"
assert_contains "$nout" "from script location"   "unset root: falls back to its own location"
assert_contains "$nout" "claude dialect"         "unset root: still identifies the dialect"
assert_contains "$nout" "structural failures: 0" "unset root: no structural failures"

rm -rf "$d" "$cur"
exit "$ASSERT_FAIL"
