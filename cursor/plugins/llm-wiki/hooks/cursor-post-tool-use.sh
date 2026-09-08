#!/usr/bin/env bash
# Cursor postToolUse uses the shared Write/Edit tool_input.file_path shape.
# Pass its payload through and translate only the model-context output field.
# The plugin root arrives as argv[1] through Cursor's command expansion.
set -uo pipefail

RAW="$(bash "${1:-}/hooks/posttooluse.sh" 2>/dev/null)"
if [[ -z "$RAW" ]]; then
    printf '{}\n'
else
    printf '%s' "$RAW" | jq -ce \
        '{additional_context: .hookSpecificOutput.additionalContext} | select(.additional_context | type == "string")' \
        2>/dev/null || printf '{}\n'
fi
exit 0
