#!/usr/bin/env bash
# test_session_context.sh -- cursor-agent conformance, cell 1: a plugin
# sessionStart hook's additional_context is delivered into the model's
# conversation under --plugin-dir.
#
# Method: a fabricated minimal plugin injects a per-run nonce via
# additional_context; the model is asked for it. The nonce exists nowhere
# the model can otherwise reach, and the session transcript (located via
# the transcript_path field of the captured hook payload) is audited for
# tool use -- any read/shell/tool activity fails the test, so a pass proves
# the nonce arrived through context injection and not through a file read
# or shell command.
#
# Byproduct: the verbatim sessionStart payload is captured for inspection
# (contains user_email and absolute paths -- do not commit it unredacted).
#
# Runs OUTSIDE tests/run.sh: spends one real cursor-agent model call.
# Needs cursor-agent on PATH, a signed-in account, and jq; exits 0 with a
# skip message when missing.
#
# Environment:
#   LLM_WIKI_HARNESS_KEEP=1  keep the scratch dir (capture + transcript)
#                            for inspection; prints its path.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

if ! command -v cursor-agent >/dev/null 2>&1; then
    echo "skip: cursor-agent not on PATH"
    exit 0
fi
if [ ! -f "${ISOLATED_CURSOR_AUTH:-$HOME/.config/cursor/auth.json}" ]; then
    echo "skip: no cursor auth file"
    exit 0
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "skip: jq not on PATH"
    exit 0
fi
echo "cursor-agent version: $(cursor-agent --version 2>/dev/null | head -1)"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $1"; }

scratch="$(mktemp -d)"
# shellcheck disable=SC2329  # invoked via trap
cleanup() {
    if [ -n "${LLM_WIKI_HARNESS_KEEP:-}" ]; then
        echo "keeping scratch: $scratch"
        return 0
    fi
    chmod -R u+rwX "$scratch" 2>/dev/null || true
    rm -rf "$scratch"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

NONCE="LWK-$(date +%s)-$$-$RANDOM"

# Fixture plugin: sessionStart captures its stdin payload verbatim into the
# plugin dir (outside the workspace, so the model cannot read it back) and
# injects the nonce as additional_context.
plugin="$scratch/probe-plugin"
mkdir -p "$plugin/.cursor-plugin" "$plugin/hooks" "$plugin/captures"
cat > "$plugin/.cursor-plugin/plugin.json" <<'EOF'
{
  "name": "session-context-probe",
  "version": "0.0.1",
  "description": "Throwaway sessionStart context-delivery probe."
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
cat > "$plugin/hooks/session-start.sh.tpl" <<'EOF'
#!/usr/bin/env bash
cat > "$1/captures/session-start.json"
printf '{"additional_context":"The session token is @NONCE@. If asked for the session token, reply with exactly this token."}\n'
EOF
sed "s/@NONCE@/$NONCE/" "$plugin/hooks/session-start.sh.tpl" > "$plugin/hooks/session-start.sh"
chmod +x "$plugin/hooks/session-start.sh"

workspace="$scratch/workspace"
mkdir -p "$workspace"

cd "$workspace" || exit 1
out="$(ISOLATED_CURSOR_ROOT="$scratch/probe" "$REPO/scripts/isolated-cursor.sh" \
    -p --trust --sandbox disabled --mode ask --output-format text \
    --plugin-dir "$plugin" \
    'What is the session token? Reply with exactly the session token and nothing else.' </dev/null 2>&1)"
rc=$?

if [ "$rc" -eq 0 ]; then ok "session exit 0"; else bad "session exit $rc: ${out:0:200}"; fi

capture="$plugin/captures/session-start.json"
if [ -s "$capture" ] && jq -e . "$capture" >/dev/null 2>&1; then
    ok "sessionStart payload captured (valid JSON)"
    event="$(jq -r '.hook_event_name // empty' "$capture")"
    if [ "$event" = "sessionStart" ]; then
        ok "payload hook_event_name is sessionStart"
    else
        bad "payload hook_event_name: '$event'"
    fi
else
    bad "no valid sessionStart payload captured"
fi

if printf '%s' "$out" | grep -qF "$NONCE"; then
    ok "nonce delivered to model via additional_context"
else
    bad "nonce absent from model output: ${out:0:200}"
fi

# Conversation-record audit: the nonce must have arrived via context
# injection alone. transcript_path is null in -p runs (probed on
# 2026.08.25-3e8eec8); the record is the chat store under the probe
# config dir -- format details in audit_chat_store.py.
tp="$(jq -r '.transcript_path // "null"' "$capture" 2>/dev/null)"
echo "  info transcript_path: $tp"
store="$(find "$scratch/probe/config/chats" -name store.db 2>/dev/null | head -1)"
if [ -n "$store" ] && [ -f "$store" ]; then
    ok "chat store found: ${store#"$scratch/"}"
    audit="$(python3 "$HERE/audit_chat_store.py" "$store" "$NONCE")"
    while IFS= read -r line; do echo "  info $line"; done <<<"$audit"
    case "$(printf '%s\n' "$audit" | grep '^nonce_roles=')" in
        *user*) ok "injected context present as conversation message" ;;
        *) bad "nonce not found in any user-role message" ;;
    esac
    tool_evidence="$(printf '%s\n' "$audit" | grep -E '^(roles|part_types)=' | grep -io 'tool[a-z_-]*' | head -5)"
    if [ -z "$tool_evidence" ]; then
        ok "no tool use in conversation (context injection was the only channel)"
    else
        bad "conversation shows tool use: $(echo "$tool_evidence" | tr '\n' ' ')"
    fi
else
    bad "no chat store found under probe config"
fi

echo "pass=$PASS fail=$FAIL"
exit "$FAIL"
