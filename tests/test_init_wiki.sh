#!/usr/bin/env bash
# L3: /wiki-init create mode (local, offline) builds .llm-wiki/ with the right
# footprint and never writes CLAUDE.md or WIKI-INDEX into the project repo.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$PLUGIN_ROOT/skills/wiki-init/scripts/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )

assert_file    "$d/.llm-wiki/index_bar.md"  "create: namespaced index_bar.md"
assert_file    "$d/.llm-wiki/log_bar.md"    "create: namespaced log_bar.md"
assert_file    "$d/.llm-wiki/SCHEMA_bar.md" "create: namespaced SCHEMA_bar.md"
assert_no_file "$d/CLAUDE.md"               "no CLAUDE.md written into project"
if ls "$d"/WIKI-INDEX*.md >/dev/null 2>&1; then _fail "WIKI-INDEX written into project root"; else _pass "no WIKI-INDEX in project root"; fi
assert_no_file "$d/.gitignore" "host .gitignore is untouched"
if git -C "$d" check-ignore -q .llm-wiki/; then _pass "wiki is ignored locally"; else _fail "wiki is not ignored"; fi
before="$(cat "$d/.git/info/exclude")"
( cd "$d" && bash "$PLUGIN_ROOT/skills/wiki-init/scripts/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )
if [[ "$(cat "$d/.git/info/exclude")" == "$before" ]]; then _pass "repeated init preserves excludes"; else _fail "repeated init changed excludes"; fi

rm -rf "$d"
exit "$ASSERT_FAIL"
