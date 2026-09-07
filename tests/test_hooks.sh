#!/usr/bin/env bash
# L2: hook behavior via the JSON stdin/stdout protocol (no live LLM).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT
HOOKS="$PLUGIN_ROOT/hooks"

# 1. SessionStart is silent when the repo has not opted in (no .llm-wiki/).
d="$(mk_scratch https://github.com/foo/bar.git)"
out="$(cd "$d" && bash "$HOOKS/session-start.sh")"
assert_empty "$out" "SessionStart silent without .llm-wiki (opt-in contract)"

# 2. With .llm-wiki/ and 7 log entries: orientation + index + exactly the last 5.
mkdir -p "$d/.llm-wiki"
printf '# Index\n- page Alpha\n' > "$d/.llm-wiki/index_bar.md"
{ echo "# Log"; for n in 1 2 3 4 5 6 7; do echo "## [2026-07-0$n] e | E$n"; echo "- body"; done; } > "$d/.llm-wiki/log_bar.md"
out="$(cd "$d" && CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$HOOKS/session-start.sh")"
# Output must be a single valid JSON object (plain stdout would be ignored by CC).
printf '%s' "$out" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
    && _pass "SessionStart emits a single valid JSON object" \
    || _fail "SessionStart output is not valid JSON"
# Visible banner rides top-level systemMessage (rendered to the user, not the model).
assert_contains "$out" '"systemMessage"' "banner uses the top-level systemMessage field"
assert_contains "$out" "durable memory active" "banner announces the wiki is active"
assert_contains "$out" "2 pages, 7 log entries" "banner reports page and log counts"
# Model-facing context rides hookSpecificOutput.additionalContext.
assert_contains "$out" '"additionalContext"' "model context uses additionalContext"
assert_contains "$out" "page Alpha" "index folded into additionalContext"
assert_contains "$out" "E7" "last-5 includes newest entry"
assert_not_contains "$out" "| E2" "last-5 excludes the 6th-newest and older"
rm -rf "$d"

# 3. PostToolUse fires on a .llm-wiki/ write, stays silent otherwise.
out="$(printf '{"tool_input":{"file_path":".llm-wiki/Foo.md"}}' | bash "$HOOKS/posttooluse.sh")"
assert_contains "$out" "Verification Gate" "PostToolUse advisory on wiki write"
printf '%s' "$out" | jq -e '.hookSpecificOutput | .hookEventName == "PostToolUse" and (.additionalContext | contains("Verification Gate"))' >/dev/null \
    && _pass "PostToolUse advisory uses model-visible additionalContext" \
    || _fail "PostToolUse advisory is not structured model context"
out="$(printf '{"tool_input":{"file_path":"src/main.py"}}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent outside .llm-wiki/"

# 3b. PostToolUse on Codex: tool_input carries only the apply_patch text, with
#     no file_path field. These two command strings are verbatim captures from a
#     live codex-cli 0.147.0 session, so the positive case is bound to the real
#     payload shape rather than to an assumption about it.
out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Update File: .llm-wiki/Alpha.md\n@@\n+- Second note.\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_contains "$out" "Verification Gate" "PostToolUse advisory on a codex apply_patch to a wiki page"

out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Add File: notes.txt\n+hello\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent on a codex apply_patch outside .llm-wiki/"

# A new wiki page and a page moved into the wiki are both writes.
out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Add File: .llm-wiki/New.md\n+x\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_contains "$out" "Verification Gate" "PostToolUse advisory on a codex apply_patch adding a wiki page"

out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Update File: notes.md\n*** Move to: .llm-wiki/Moved.md\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_contains "$out" "Verification Gate" "PostToolUse advisory on a page moved into the wiki"

# One apply_patch can touch several files. The advisory must fire once, not once
# per file, and must not be missed because the wiki page is not the first entry.
out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Update File: src/main.py\n+x\n*** Update File: .llm-wiki/Alpha.md\n+y\n*** Update File: README.md\n+z\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_contains "$out" "Verification Gate" "PostToolUse advisory on a multi-file patch touching a wiki page"
[ "$(printf '%s' "$out" | grep -c 'Verification Gate')" = "1" ] \
    && _pass "PostToolUse advisory fires once per patch, not once per file" \
    || _fail "PostToolUse advisory repeated within a single patch"

# A shell redirect into the wiki reports as tool_name Bash and carries no patch
# markers. The emitted codex matcher is apply_patch so this payload never
# reaches the script in practice; asserting it here pins the known blind spot so
# a future matcher widening has to change this line deliberately.
out="$(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"printf x > .llm-wiki/Beta.md"}}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent on a shell write into .llm-wiki/ (known gap)"

# Nothing in the patch grammar may be mistaken for a target.
out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Delete File: .llm-wiki/Old.md\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent on a wiki page deletion"

out="$(printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Update File: .llm-wiki/notes.txt\n+x\n*** End Patch"}}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent on a non-markdown file inside .llm-wiki/"

out="$(printf '%s' '{}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent on a payload with no tool_input"

# 4. Opt-in: a repo WITH a GitHub wiki but no .llm-wiki/ stays silent (no auto-clone).
#    Points at a real wiki-bearing repo; the opt-in hook returns before any
#    network, so this is deterministic and offline. Attaching is /wiki-init's job.
d="$(mk_scratch https://github.com/chrissweet/llm-wiki-vision.git)"
out="$(cd "$d" && python3 "$HOOKS/ensure-wiki.py" 2>/dev/null)"
assert_empty "$out" "ensure-wiki silent when .llm-wiki absent (no auto-clone even if a GitHub wiki exists)"
assert_no_file "$d/.llm-wiki" "ensure-wiki does not attach; that is /wiki-init's job"
rm -rf "$d"

exit "$ASSERT_FAIL"
