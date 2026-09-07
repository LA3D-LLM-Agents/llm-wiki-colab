#!/usr/bin/env bash
#
# Cursor sessionStart adapter for the llm-wiki plugin.
#
# argv[1] : plugin root. Cursor expands ${CURSOR_PLUGIN_ROOT} textually in the
#           hooks.json command string and nowhere else, and exports no
#           plugin-root variable, so the path has to arrive as an argument.
# stdin   : Cursor sessionStart payload (common schema + session fields).
# stdout  : Cursor sessionStart output {"additional_context": ..., "env": {...}}
#
# What it does, in order:
#   1. export CLAUDE_PLUGIN_ROOT, which is how the shared hooks find core/.
#   2. chdir to the workspace root. The hook process starts in the plugin root,
#      not the workspace, and session-start.py decides whether this repo has
#      opted in by testing `.llm-wiki` against $PWD.
#   3. run the shared coordinator, which orders the installed stages.
#   4. translate the Claude-dialect JSON into Cursor's field names.
#
# Fail open at every step: sessionStart is fire-and-forget, and a session that
# starts without orientation is a degraded session, while one that hangs or
# errors out is a broken harness. Every failure path still prints valid JSON
# and exits 0.
#
# Dependencies: bash and python3, both already required by the shared hooks.

set -uo pipefail

emit_empty() {
    printf '{"additional_context":""}'
}

PAYLOAD="$(cat 2>/dev/null || true)"
CWD_BEFORE="$PWD"
PLUGIN_ROOT="${1:-}"

if [[ -z "$PLUGIN_ROOT" || ! -d "$PLUGIN_ROOT" ]]; then
    emit_empty
    exit 0
fi

export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"

# --- resolve the workspace root -------------------------------------------
# CURSOR_PROJECT_DIR is what the CLI sets; workspace_roots[0] from the payload
# is the documented equivalent; $PWD is the last resort and is the plugin root,
# where the opt-in probe correctly finds no wiki and stays silent.
ROOT="${CURSOR_PROJECT_DIR:-}"
if [[ -z "$ROOT" ]]; then
    ROOT="$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
r = d.get("workspace_roots") or []
print(r[0] if r else "")
' 2>/dev/null || true)"
fi
[[ -n "$ROOT" ]] || ROOT="$CWD_BEFORE"
cd "$ROOT" 2>/dev/null || true

# Run the shared coordinator and preserve all stage diagnostics.
RAW="$(printf '%s' "$PAYLOAD" | python3 "$PLUGIN_ROOT/hooks/session-start.py" 2>/dev/null)"

# --- translate Claude dialect -> Cursor dialect ----------------------------
# systemMessage has no Cursor counterpart and is dropped: Cursor renders no
# user-visible hook banner. `env` propagates to later hook executions in this
# session (it does not reach the agent's own shell), which is why the skills
# resolve the plugin root by another route entirely.
OUT="$(LW_RAW="${RAW:-}" LW_ROOT="$PLUGIN_ROOT" python3 -c '
import json, os, sys
raw = os.environ.get("LW_RAW", "").strip()
ctx = ""
if raw:
    try:
        d = json.loads(raw)
        ctx = ((d.get("hookSpecificOutput") or {}).get("additionalContext") or "")
    except Exception:
        ctx = ""
sys.stdout.write(json.dumps({
    "additional_context": ctx,
    "env": {"CLAUDE_PLUGIN_ROOT": os.environ["LW_ROOT"]},
}))
' 2>/dev/null)"
TRC=$?

if [[ $TRC -ne 0 || -z "$OUT" ]]; then
    emit_empty
    exit 0
fi

printf '%s' "$OUT"
exit 0
