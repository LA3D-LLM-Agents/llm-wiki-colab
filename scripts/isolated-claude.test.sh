#!/usr/bin/env bash
# isolated-claude.test.sh -- canary for the facts scripts/isolated-claude.sh
# is built on, so a new claude release that changes them is caught here rather
# than in a confusing conformance-test failure.
#
# Fabricates a minimal plugin whose SessionStart hook records what it saw
# in-session, drives it through the wrapper, and checks:
#   1. an empty config dir reports logged-out (built-in red: the auth
#      detector can fire the other way),
#   2. the copied credentials register as logged in inside the probe,
#   3. the injected SessionStart hook executes and saw the redirected HOME
#      and CLAUDE_CONFIG_DIR,
#   4. the session transcript lands under the probe CLAUDE_CONFIG_DIR
#      (this also witnesses the nested-session persistence handling when the
#      canary itself runs inside a claude session),
#   5. the raw API-body capture spooled into the probe root,
#   6. no official/pinned marketplace materialized (seed-dir starvation),
#   7. nothing fell back to $HOME/.claude inside the probe,
#   8. the credentials copy does not survive the run,
#   9. nothing was written to the real ~/.claude or ~/.claude.json
#      (skipped with a note when running inside a claude session, whose own
#      writes to the real state would false-positive the check).
#
# Checks 1-2 are free; the rest ride one claude model call.  Needs claude on
# PATH and a signed-in account; exits 0 with a skip message when either is
# missing.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! command -v claude >/dev/null 2>&1; then
    echo "skip: claude not on PATH"
    exit 0
fi
if [ ! -f "${ISOLATED_CLAUDE_AUTH:-$HOME/.claude/.credentials.json}" ]; then
    echo "skip: no claude credentials file"
    exit 0
fi
echo "claude version: $(claude --version 2>/dev/null | head -1)"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $1"; }

scratch="$(mktemp -d)"
probe="$scratch/probe"
# shellcheck disable=SC2329  # invoked via trap
cleanup() {
    chmod -R u+rwX "$scratch" 2>/dev/null || true
    rm -rf "$scratch"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Minimal plugin: SessionStart hook writes a sentinel into the plugin dir
# itself (its own root arrives as $1, so no dependency on the hook's cwd) and
# records the HOME and CLAUDE_CONFIG_DIR the session actually ran with.  The
# hook prints nothing: SessionStart stdout becomes injected context, and the
# canary asserts wrapper facts, not context delivery (that is a conformance
# cell).
plugin="$scratch/canary-plugin"
mkdir -p "$plugin/.claude-plugin" "$plugin/hooks"
cat > "$plugin/.claude-plugin/plugin.json" <<'EOF'
{
  "name": "isolated-claude-canary",
  "version": "0.0.1",
  "description": "Throwaway SessionStart canary for isolated-claude.sh."
}
EOF
cat > "$plugin/hooks/hooks.json" <<'EOF'
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh\" \"${CLAUDE_PLUGIN_ROOT}\""
          }
        ]
      }
    ]
  }
}
EOF
cat > "$plugin/hooks/session-start.sh" <<'EOF'
#!/usr/bin/env bash
{
    echo "home=$HOME"
    echo "config=${CLAUDE_CONFIG_DIR:-unset}"
} > "$1/SENTINEL"
EOF
chmod +x "$plugin/hooks/session-start.sh"

workspace="$scratch/workspace"
mkdir -p "$workspace"

wrapped() {
    (cd "$workspace" && ISOLATED_CLAUDE_ROOT="$probe" "$HERE/isolated-claude.sh" "$@" </dev/null 2>>"$scratch/wrapper-stderr.log")
}

# Built-in red for the auth detector: an empty config dir must report
# logged-out, or the logged-in check below proves nothing.  Output is
# captured so a failure carries its evidence.
empty="$scratch/empty"
mkdir -p "$empty/config" "$empty/home"
red_out="$(env CLAUDE_CONFIG_DIR="$empty/config" HOME="$empty/home" claude auth status 2>&1)"
if printf '%s' "$red_out" | grep -q '"loggedIn": false'; then
    ok "empty config dir reports logged-out (auth detector can go red)"
else
    bad "empty config dir did not report logged-out: $(printf '%s' "$red_out" | tr '\n' ' ' | head -c 200)"
fi

green_out="$(wrapped auth status)"
if printf '%s' "$green_out" | grep -q '"loggedIn": true'; then
    ok "copied credentials register as logged in"
else
    bad "not logged in with copied credentials: $(printf '%s' "$green_out" | tr '\n' ' ' | head -c 200)"
fi

marker="$scratch/marker"
touch "$marker"
sleep 1

# Low-class model by default: the canary asserts wrapper facts, not model
# quality.  Override with ISOLATED_CLAUDE_TEST_MODEL if the alias breaks.
sid="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen)"
out="$(wrapped -p --max-budget-usd 1 --session-id "$sid" \
    --model "${ISOLATED_CLAUDE_TEST_MODEL:-haiku}" \
    --plugin-dir "$plugin" \
    'Reply with exactly: OK')"
rc=$?
if [ "$rc" -eq 0 ]; then ok "session exit 0"; else bad "session exit $rc: $(tail -2 "$scratch/wrapper-stderr.log" | tr '\n' ' ')"; fi

if printf '%s' "$out" | grep -q 'OK'; then
    ok "model replied through copied credentials"
else
    bad "no OK in output: ${out:0:120}"
fi

if [ -f "$plugin/SENTINEL" ]; then
    ok "injected SessionStart hook executed"
    if grep -qx "home=$probe/home" "$plugin/SENTINEL"; then
        ok "hook saw redirected HOME"
    else
        bad "hook saw wrong HOME: $(grep '^home=' "$plugin/SENTINEL")"
    fi
    if grep -qx "config=$probe/claude" "$plugin/SENTINEL"; then
        ok "hook saw redirected CLAUDE_CONFIG_DIR"
    else
        bad "hook saw wrong config dir: $(grep '^config=' "$plugin/SENTINEL")"
    fi
else
    bad "injected SessionStart hook did not run (no SENTINEL)"
fi

if [ -n "$(find "$probe/claude/projects" -name "$sid.jsonl" 2>/dev/null | head -1)" ]; then
    ok "transcript landed under probe CLAUDE_CONFIG_DIR"
else
    bad "no transcript $sid.jsonl under $probe/claude/projects"
fi

if [ -n "$(find "$probe/api-bodies" -type f 2>/dev/null | head -1)" ]; then
    ok "raw API bodies spooled into probe root"
else
    bad "no API-body capture in $probe/api-bodies"
fi

if [ -z "$(grep -rl 'claude-plugins-official' "$probe/claude/plugins" 2>/dev/null | head -1)" ]; then
    ok "no official/pinned marketplace materialized"
else
    bad "claude-plugins-official present in probe plugin state"
fi

if [ ! -e "$probe/home/.claude" ]; then
    ok "nothing fell back to \$HOME/.claude inside the probe"
else
    bad "state fell back to probe \$HOME/.claude: $(find "$probe/home/.claude" -maxdepth 2 | head -3 | tr '\n' ' ')"
fi

if [ ! -e "$probe/claude/.credentials.json" ]; then
    ok "credentials copy did not survive the run"
else
    bad "credentials copy survived in probe root"
fi

# A claude session writes its own real state continuously, so this check can
# only run outside one; the probe-root twin below stays meaningful either way.
if [ -n "${CLAUDECODE:-}" ]; then
    echo "  skip real-state write check (running inside a claude session)"
else
    real_writes="$(find "$HOME/.claude" "$HOME/.claude.json" -newer "$marker" 2>/dev/null)"
    if [ -z "$real_writes" ]; then
        ok "no writes to real claude state"
    else
        bad "real claude state touched: $(echo "$real_writes" | head -3 | tr '\n' ' ')"
    fi
fi

# The same predicate must fire on the probe root, or the check above is
# vacuous (a detector that has never gone red proves nothing).
if [ -n "$(find "$probe" -newer "$marker" 2>/dev/null | head -1)" ]; then
    ok "write detector fires on probe root"
else
    bad "write detector saw nothing in probe root; isolation check is vacuous"
fi

echo "pass=$PASS fail=$FAIL"
exit "$FAIL"
