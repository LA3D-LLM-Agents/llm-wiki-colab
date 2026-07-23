#!/usr/bin/env bash
# Regression test for the divergence quirk: /wiki-init attach to an existing
# wiki must be idempotent, no SCHEMA rewrite, no page stamping, no gratuitous
# log entry, and above all NO new commit (an un-pushed local commit is what
# diverged a clone from the pushed wiki).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

d="$(mk_scratch https://github.com/foo/bar.git)"

# First run: create mode (scaffolds the wiki, one "Initialize" commit).
( cd "$d" && bash "$ROOT/core/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )
head1="$(git -C "$d/.llm-wiki" rev-parse HEAD)"

# Second run: the wiki now has a SCHEMA, so this is update-mode (attach).
out="$(cd "$d" && bash "$ROOT/core/init-wiki.sh" --agent claude-code 2>&1)"
head2="$(git -C "$d/.llm-wiki" rev-parse HEAD)"

[ "$head1" = "$head2" ] && _pass "re-attach makes no new commit (HEAD unchanged)" || _fail "re-attach created a commit ($head1 -> $head2)"
assert_contains "$out" "No wiki changes to commit" "re-attach reports no changes"
[ -z "$(git -C "$d/.llm-wiki" status --porcelain)" ] && _pass "wiki working tree clean after re-attach" || _fail "re-attach left the wiki dirty"

rm -rf "$d"
exit "$ASSERT_FAIL"
