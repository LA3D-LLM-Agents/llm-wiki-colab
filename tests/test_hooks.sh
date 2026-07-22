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

# 4. ensure-wiki state-3: origin with no GitHub wiki -> create-first-page prompt, no attach.
d="$(mk_scratch https://github.com/this-owner-does-not-exist-zzz/no-such-repo.git)"
out="$(cd "$d" && python3 "$HOOKS/ensure-wiki.py" 2>/dev/null)"
assert_contains "$out" "no GitHub wiki yet" "ensure-wiki state-3 create-first-page prompt"
assert_no_file "$d/.llm-wiki" "state-3 does not attach anything"
rm -rf "$d"

exit "$ASSERT_FAIL"
