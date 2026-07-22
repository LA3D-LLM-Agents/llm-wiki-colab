#!/usr/bin/env bash
# L2: hook behavior via the JSON stdin/stdout protocol (no live LLM).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"
HOOKS="$ROOT/adapters/claude-code/hooks"

# 1. SessionStart is silent when the repo has not opted in (no .llm-wiki/).
d="$(mk_scratch https://github.com/foo/bar.git)"
out="$(cd "$d" && bash "$HOOKS/session-start.sh")"
assert_empty "$out" "SessionStart silent without .llm-wiki (opt-in contract)"

# 2. With .llm-wiki/ and 7 log entries: orientation + index + exactly the last 5.
mkdir -p "$d/.llm-wiki"
printf '# Index\n- page Alpha\n' > "$d/.llm-wiki/index_bar.md"
{ echo "# Log"; for n in 1 2 3 4 5 6 7; do echo "## [2026-07-0$n] e | E$n"; echo "- body"; done; } > "$d/.llm-wiki/log_bar.md"
out="$(cd "$d" && CLAUDE_PLUGIN_ROOT="$ROOT/adapters/claude-code" bash "$HOOKS/session-start.sh")"
assert_contains "$out" "durable memory" "orientation emitted"
assert_contains "$out" "page Alpha" "index emitted"
assert_contains "$out" "E7" "last-5 includes newest entry"
assert_not_contains "$out" "| E2" "last-5 excludes the 6th-newest and older"
rm -rf "$d"

# 3. PostToolUse fires on a .llm-wiki/ write, stays silent otherwise.
out="$(printf '{"tool_input":{"file_path":".llm-wiki/Foo.md"}}' | bash "$HOOKS/posttooluse.sh")"
assert_contains "$out" "Verification Gate" "PostToolUse advisory on wiki write"
out="$(printf '{"tool_input":{"file_path":"src/main.py"}}' | bash "$HOOKS/posttooluse.sh")"
assert_empty "$out" "PostToolUse silent outside .llm-wiki/"

# 4. Opt-in: a repo WITH a GitHub wiki but no .llm-wiki/ stays silent (no auto-clone).
#    Points at a real wiki-bearing repo; the opt-in hook returns before any
#    network, so this is deterministic and offline. Attaching is /wiki-init's job.
d="$(mk_scratch https://github.com/chrissweet/llm-wiki-vision.git)"
out="$(cd "$d" && python3 "$HOOKS/ensure-wiki.py" 2>/dev/null)"
assert_empty "$out" "ensure-wiki silent when .llm-wiki absent (no auto-clone even if a GitHub wiki exists)"
assert_no_file "$d/.llm-wiki" "ensure-wiki does not attach; that is /wiki-init's job"
rm -rf "$d"

exit "$ASSERT_FAIL"
