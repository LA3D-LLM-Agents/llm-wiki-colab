#!/usr/bin/env bash
#
# Cursor preToolUse adapter for the llm-wiki plugin.
#
# argv[1] : plugin root. Cursor expands ${CURSOR_PLUGIN_ROOT} textually in the
#           hooks.json command string, so the path arrives as an argument.
#           $CLAUDE_PLUGIN_ROOT and $CURSOR_PLUGIN_ROOT, both exported into hook
#           processes, are the fallbacks if argv[1] is missing.
# stdin   : Cursor preToolUse payload (common schema + tool_name/tool_input).
# stdout  : Cursor preToolUse output {"permission": "allow", "updated_input": ...}
#
# What it does: a Shell command the agent is about to run gets
# `export CLAUDE_PLUGIN_ROOT=<root>; ` prefixed onto it, so the shell the skill
# bodies target observes the plugin root. The agent's shell inherits nothing
# from the session: sessionStart's `env` reaches later hook processes only, and
# no plugin-root variable exists there otherwise, so a skill body that shells
# out through the variable would fail with exit 127. Rewriting the command is
# the one channel that reaches that process.
#
# The prefix is semantically inert: one variable export, then the original
# command byte-for-byte. Other tool_input fields ride through unchanged.
#
# Fail open at every step: anything other than a well-formed Shell payload emits
# a bare allow and the command runs unmodified. Never exit 2, never deny; a
# broken adapter must cost the plugin root, not the agent's ability to run
# commands.
#
# Dependencies: bash and python3, both already required by the shared hooks.

set -uo pipefail

emit_allow() {
    printf '{"permission":"allow"}'
}

PAYLOAD="$(cat 2>/dev/null || true)"

PLUGIN_ROOT="${1:-}"
[[ -n "$PLUGIN_ROOT" ]] || PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
[[ -n "$PLUGIN_ROOT" ]] || PLUGIN_ROOT="${CURSOR_PLUGIN_ROOT:-}"

if [[ -z "$PLUGIN_ROOT" ]]; then
    emit_allow
    exit 0
fi

# shlex.quote the root rather than double-quoting it here: an install path is
# SHA-keyed and unknown at build time, and one quoting bug would corrupt every
# command the agent runs for the rest of the session.
OUT="$(printf '%s' "$PAYLOAD" | LW_ROOT="$PLUGIN_ROOT" python3 -c '
import json, os, shlex, sys

out = {"permission": "allow"}
try:
    payload = json.load(sys.stdin)
except Exception:
    payload = None

if isinstance(payload, dict) and payload.get("tool_name") == "Shell":
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str) and command:
            updated = dict(tool_input)
            updated["command"] = "export CLAUDE_PLUGIN_ROOT={}; {}".format(
                shlex.quote(os.environ["LW_ROOT"]), command
            )
            out["updated_input"] = updated

sys.stdout.write(json.dumps(out))
' 2>/dev/null)"
RC=$?

if [[ $RC -ne 0 || -z "$OUT" ]]; then
    emit_allow
    exit 0
fi

printf '%s' "$OUT"
exit 0
