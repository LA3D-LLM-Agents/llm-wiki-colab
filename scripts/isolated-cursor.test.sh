#!/usr/bin/env bash
# isolated-cursor.test.sh -- canary for the facts scripts/isolated-cursor.sh
# is built on, so a new cursor-agent release that changes them is caught here
# rather than in a confusing conformance-test failure.
#
# Fabricates a minimal plugin whose sessionStart hook writes a sentinel file
# recording what it saw in-session, runs it through the wrapper with
# --plugin-dir, and checks:
#   1. the isolated session runs and the injected hook executes,
#   2. the hook saw the redirected HOME and a read-only (555) plugins dir,
#   3. nothing was written to the real ~/.cursor or ~/.config/cursor,
#   4. no account plugin materialized into the probe root.
#
# Spends one real cursor-agent model call. Needs cursor-agent on PATH and a
# signed-in account; exits 0 with a skip message when either is missing.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! command -v cursor-agent >/dev/null 2>&1; then
    echo "skip: cursor-agent not on PATH"
    exit 0
fi
if [ ! -f "${ISOLATED_CURSOR_AUTH:-$HOME/.config/cursor/auth.json}" ]; then
    echo "skip: no cursor auth file"
    exit 0
fi
echo "cursor-agent version: $(cursor-agent --version 2>/dev/null | head -1)"

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

# Minimal plugin: sessionStart writes a sentinel into the plugin dir itself
# (its own root arrives as $1, so no dependency on the hook's cwd) and records
# the HOME and plugins-dir mode the session actually ran with.
plugin="$scratch/canary-plugin"
mkdir -p "$plugin/.cursor-plugin" "$plugin/hooks"
cat > "$plugin/.cursor-plugin/plugin.json" <<'EOF'
{
  "name": "isolated-cursor-canary",
  "version": "0.0.1",
  "description": "Throwaway sessionStart canary for isolated-cursor.sh."
}
EOF
cat > "$plugin/hooks/hooks.json" <<'EOF'
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "command",
        "command": "bash \"${CURSOR_PLUGIN_ROOT}/hooks/session-start.sh\" \"${CURSOR_PLUGIN_ROOT}\""
      }
    ]
  }
}
EOF
cat > "$plugin/hooks/session-start.sh" <<'EOF'
#!/usr/bin/env bash
{
    echo "home=$HOME"
    echo "plugins_mode=$(stat -c %a "$HOME/.cursor/plugins" 2>/dev/null || stat -f %Lp "$HOME/.cursor/plugins" 2>/dev/null || echo missing)"
} > "$1/SENTINEL"
printf '{"additional_context":""}\n'
EOF
chmod +x "$plugin/hooks/session-start.sh"

workspace="$scratch/workspace"
mkdir -p "$workspace"
marker="$scratch/marker"
touch "$marker"
sleep 1

# The canary tests the starved recipe specifically; an inherited
# ISOLATED_CURSOR_ALLOW_ACCOUNT_PLUGINS would silently flip both starvation
# checks red (verified: mode 755 + account plugin materialized).
unset ISOLATED_CURSOR_ALLOW_ACCOUNT_PLUGINS

cd "$workspace" || exit 1
# Cheapest tier by default: auto-smart[optimize_for=cost] is the flat-price
# bundled Auto tier (tracks the current auto routing); a bare `auto` maps to
# the metered `balanced` tier at roughly twice the price (probed 2026-08,
# cursor Router).  The canary asserts wrapper facts, not model quality.
# Override with ISOLATED_CURSOR_TEST_MODEL if the tier syntax rotates.
out="$(ISOLATED_CURSOR_ROOT="$probe" "$HERE/isolated-cursor.sh" \
    -p --trust --sandbox disabled --mode ask --output-format text \
    --model "${ISOLATED_CURSOR_TEST_MODEL:-auto-smart[optimize_for=cost]}" \
    --plugin-dir "$plugin" \
    'Reply with exactly: OK' </dev/null 2>&1)"
rc=$?

if [ "$rc" -eq 0 ]; then ok "session exit 0"; else bad "session exit $rc: ${out:0:200}"; fi

if [ -f "$plugin/SENTINEL" ]; then
    ok "injected sessionStart hook executed"
    if grep -qx "home=$probe/home" "$plugin/SENTINEL"; then
        ok "hook saw redirected HOME"
    else
        bad "hook saw wrong HOME: $(grep '^home=' "$plugin/SENTINEL")"
    fi
    if grep -qx "plugins_mode=555" "$plugin/SENTINEL"; then
        ok "plugins dir was read-only in-session"
    else
        bad "plugins dir not starved: $(grep '^plugins_mode=' "$plugin/SENTINEL")"
    fi
else
    bad "injected sessionStart hook did not run (no SENTINEL)"
fi

real_writes="$(find "$HOME/.cursor" "$HOME/.config/cursor" -newer "$marker" 2>/dev/null)"
if [ -z "$real_writes" ]; then
    ok "no writes to real cursor state"
else
    bad "real cursor state touched: $(echo "$real_writes" | head -3 | tr '\n' ' ')"
fi

# The same predicate must fire on the probe root, or the check above is
# vacuous (a detector that has never gone red proves nothing).
if [ -n "$(find "$probe" -newer "$marker" 2>/dev/null | head -1)" ]; then
    ok "write detector fires on probe root"
else
    bad "write detector saw nothing in probe root; isolation check is vacuous"
fi

# Discriminating only when the account has plugins installed; still a valid
# guard when it does not.
if [ -z "$(find "$probe/home/.cursor/plugins" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
    ok "no account plugin materialized"
else
    bad "account plugin materialized despite 555 block"
fi

echo "pass=$PASS fail=$FAIL"
exit "$FAIL"
