#!/usr/bin/env bash
# L3: /wiki-init create mode (local, offline) builds .llm-wiki/ with the right
# footprint and never writes CLAUDE.md or WIKI-INDEX into the project repo.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$ROOT/core/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )

assert_file    "$d/.llm-wiki/index_bar.md"  "create: namespaced index_bar.md"
assert_file    "$d/.llm-wiki/log_bar.md"    "create: namespaced log_bar.md"
assert_file    "$d/.llm-wiki/SCHEMA_bar.md" "create: namespaced SCHEMA_bar.md"
assert_no_file "$d/CLAUDE.md"               "no CLAUDE.md written into project"
if ls "$d"/WIKI-INDEX*.md >/dev/null 2>&1; then _fail "WIKI-INDEX written into project root"; else _pass "no WIKI-INDEX in project root"; fi
assert_grep_file "$d/.gitignore" ".llm-wiki/" "gitignore ignores .llm-wiki/"

rm -rf "$d"
exit "$ASSERT_FAIL"
