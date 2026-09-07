#!/usr/bin/env bash
# Built registration and protocol translation for Cursor's wiki-write advisory.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env CURSOR_PLUGIN_ROOT
ADAPTER="$CURSOR_PLUGIN_ROOT/hooks/cursor-post-tool-use.sh"
HOOKS="$CURSOR_PLUGIN_ROOT/hooks/hooks.json"
jq -e '.hooks.postToolUse | length == 1 and .[0].type == "command" and .[0].matcher == "Write|Edit"' "$HOOKS" >/dev/null \
    && _pass "Cursor registers one Write/Edit postToolUse advisory" \
    || _fail "Cursor postToolUse registration is missing or incorrect"
assert_contains "$(jq -r '.hooks.postToolUse[0].command' "$HOOKS")" \
    'bash "${CURSOR_PLUGIN_ROOT}/hooks/cursor-post-tool-use.sh" "${CURSOR_PLUGIN_ROOT}"' \
    "Cursor invokes advisory adapter with plugin root"
for tool in Write Edit; do
    out="$(printf '{"tool_name":"%s","tool_input":{"file_path":"/tmp/project/.llm-wiki/page.md"}}' "$tool" | bash "$ADAPTER" "$CURSOR_PLUGIN_ROOT")"
    printf '%s' "$out" | jq -e '.additional_context | contains("A wiki page was just written or edited.") and contains("Verification Gate")' >/dev/null \
        && _pass "Cursor $tool receives the shared advisory as additional_context" \
        || _fail "Cursor $tool advisory is missing"
done
for payload in '{"tool_input":{"file_path":"src/main.py"}}' '{}' 'invalid'; do
    out="$(printf '%s' "$payload" | bash "$ADAPTER" "$CURSOR_PLUGIN_ROOT")"
    [ "$out" = '{}' ] && _pass "Cursor emits no context for an unrelated or malformed payload" \
        || _fail "Cursor emitted unexpected context"
done
exit "$ASSERT_FAIL"
