#!/usr/bin/env bash
# L2: Cursor hook behavior via the JSON stdin/stdout protocol (no live LLM).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"
HOOKS="$ROOT/adapters/cursor/hooks"

# 1. sessionStart emits empty additional_context when the repo has not opted in.
d="$(mk_scratch https://github.com/foo/bar.git)"
out="$(cd "$d" && printf '{}' | bash "$HOOKS/session-start.sh")"
printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("additional_context","x")==""' 2>/dev/null \
    && _pass "sessionStart empty additional_context without .llm-wiki (opt-in)" \
    || _fail "sessionStart should emit empty additional_context without .llm-wiki"

# 2. With .llm-wiki/ and 7 log entries: orientation + index + exactly the last 5.
mkdir -p "$d/.llm-wiki"
printf '# Index\n- page Alpha\n' > "$d/.llm-wiki/index_bar.md"
{ echo "# Log"; for n in 1 2 3 4 5 6 7; do echo "## [2026-07-0$n] e | E$n"; echo "- body"; done; } > "$d/.llm-wiki/log_bar.md"
out="$(cd "$d" && printf '{}' | CURSOR_PLUGIN_ROOT="$ROOT/adapters/cursor" bash "$HOOKS/session-start.sh")"
printf '%s' "$out" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
    && _pass "sessionStart emits a single valid JSON object" \
    || _fail "sessionStart output is not valid JSON"
assert_contains "$out" '"additional_context"' "model context uses additional_context"
assert_contains "$out" "durable memory active" "banner announces the wiki is active"
assert_contains "$out" "2 pages, 7 log entries" "banner reports page and log counts"
assert_contains "$out" "page Alpha" "index folded into additional_context"
assert_contains "$out" "E7" "last-5 includes newest entry"
assert_not_contains "$out" "| E2" "last-5 excludes the 6th-newest and older"
rm -rf "$d"

# 3. postToolUse fires on a .llm-wiki/ write, stays empty otherwise.
out="$(printf '{"tool_input":{"file_path":".llm-wiki/Foo.md"}}' | bash "$HOOKS/posttooluse.sh")"
printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "Verification Gate" in d.get("additional_context","")' 2>/dev/null \
    && _pass "postToolUse advisory on wiki write" \
    || _fail "postToolUse should nudge Verification Gate on wiki write"
out="$(printf '{"tool_input":{"file_path":"src/main.py"}}' | bash "$HOOKS/posttooluse.sh")"
printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("additional_context","x")==""' 2>/dev/null \
    && _pass "postToolUse empty outside .llm-wiki/" \
    || _fail "postToolUse should emit empty additional_context outside .llm-wiki/"

# 4. ensure-wiki wrapper: silent (empty context) when .llm-wiki absent.
d="$(mk_scratch https://github.com/chrissweet/llm-wiki-vision.git)"
out="$(cd "$d" && printf '{}' | bash "$HOOKS/ensure-wiki.sh" 2>/dev/null)"
printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("additional_context","x")==""' 2>/dev/null \
    && _pass "ensure-wiki empty when .llm-wiki absent (no auto-clone)" \
    || _fail "ensure-wiki should emit empty additional_context when .llm-wiki absent"
assert_no_file "$d/.llm-wiki" "ensure-wiki does not attach; that is /wiki-init's job"
rm -rf "$d"

exit "$ASSERT_FAIL"
