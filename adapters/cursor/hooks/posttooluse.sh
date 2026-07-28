#!/usr/bin/env bash
#
# Cursor postToolUse hook (advisory): after a Write or Edit to a wiki page,
# remind the agent to run the Verification Gate before committing.
#
# Advisory only: always emits a single JSON object with additional_context
# (empty for non-wiki writes) and exits 0. Does not evaluate the wiki itself.
#
# Reads the postToolUse event JSON on stdin.

set -uo pipefail

INPUT=$(cat)

emit() {
    # stdin = additional_context message (may be empty)
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys; print(json.dumps({"additional_context": sys.stdin.read()}))'
    elif command -v jq >/dev/null 2>&1; then
        jq -Rs '{additional_context: .}'
    else
        cat >/dev/null
        printf '%s\n' '{"additional_context":""}'
    fi
}

FILE_PATH=""
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
elif command -v python3 >/dev/null 2>&1; then
    FILE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", "") or "")
except Exception:
    print("")' 2>/dev/null || true)
fi

case "$FILE_PATH" in
    */.llm-wiki/*.md|.llm-wiki/*.md)
        emit <<'EOF'
A wiki page was just written or edited. Before committing in the wiki
repo, run the Verification Gate (core/agents/verification-gate.md in the
llm-wiki plugin) over every page created or edited this session: every
numerical claim tagged with its corpus, every projection marked as such,
back-references bidirectional, and the index plus log updated. This is an
advisory reminder and does not block.
EOF
        exit 0
        ;;
esac

printf '' | emit
exit 0
