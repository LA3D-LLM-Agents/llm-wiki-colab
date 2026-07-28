#!/usr/bin/env bash
#
# Cursor sessionStart hook: thin adapter over ensure-wiki.py.
#
# ensure-wiki.py emits Claude SessionStart JSON when it has a nudge:
#   {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}
# Cursor sessionStart expects:
#   {"additional_context":"..."}
#
# Maps silence to {"additional_context":""} and a nudge to additional_context.
# Fail-open: any unexpected condition degrades to empty context + exit 0.
#

set -uo pipefail

# Drain stdin (Cursor sends sessionStart input JSON).
cat >/dev/null

emit_empty() {
    printf '%s\n' '{"additional_context":""}'
    exit 0
}

command -v python3 >/dev/null 2>&1 || emit_empty

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENSURE_PY="$HERE/ensure-wiki.py"
[[ -f "$ENSURE_PY" ]] || emit_empty

RAW="$(python3 "$ENSURE_PY" 2>/dev/null)" || emit_empty

[[ -z "$RAW" ]] && emit_empty

printf '%s' "$RAW" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    msg = data.get("hookSpecificOutput", {}).get("additionalContext", "")
except Exception:
    msg = ""
print(json.dumps({"additional_context": msg if isinstance(msg, str) else ""}))
' || emit_empty

exit 0
