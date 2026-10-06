#!/usr/bin/env bash
# L3: several sessions can start in one repository at once, and linked
# worktrees share a single exclude file, so the session-start hook must be
# safe to run concurrently and must not be blocked by anything another run,
# or an older plugin version, left behind.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

new_host() {
    local host
    host="$(mk_scratch)"
    git init -q "$host/.llm-wiki"
    printf '# personal excludes\n' > "$host/.git/info/exclude"
    echo "$host"
}
run_hook() { (cd "$1" && python3 "$PLUGIN_ROOT/hooks/session-start.py" 2>&1 </dev/null); }

# Older versions took an exclude.lock and could leave it behind after a crash.
host="$(new_host)"
printf 'left by an earlier run' > "$host/.git/info/exclude.lock"
out="$(run_hook "$host")"
assert_not_contains "$out" "could not ensure the local wiki ignore rule" \
    "leftover lock: hook reports no exclude failure"
if git -C "$host" check-ignore -q .llm-wiki/; then
    _pass "leftover lock: git ignores the wiki"
else
    _fail "leftover lock: git does not ignore the wiki"
fi
[ "$(cat "$host/.git/info/exclude.lock")" = "left by an earlier run" ] \
    && _pass "leftover lock: a file the hook does not own is untouched" \
    || _fail "leftover lock: the hook modified a file it does not own"
rm -rf "$host"

# Every concurrent start must succeed, and together they add the rule once.
host="$(new_host)"
outputs="$(mktemp -d)"
before="$(wc -l < "$host/.git/info/exclude")"
for n in 1 2 3 4 5 6 7 8; do
    run_hook "$host" > "$outputs/$n" &
done
wait
warned="$(grep -l "could not ensure the local wiki ignore rule" "$outputs"/* 2>/dev/null | wc -l)"
[ "$warned" -eq 0 ] \
    && _pass "concurrent: no session reports an exclude failure" \
    || _fail "concurrent: $warned of 8 sessions reported an exclude failure"
if git -C "$host" check-ignore -q .llm-wiki/; then
    _pass "concurrent: git ignores the wiki"
else
    _fail "concurrent: git does not ignore the wiki"
fi
after="$(wc -l < "$host/.git/info/exclude")"
[ "$after" -eq $((before + 1)) ] \
    && _pass "concurrent: the exclude file gained exactly one line" \
    || _fail "concurrent: the exclude file went from $before to $after lines"
left="$(ls -A "$host/.git/info" | tr '\n' ' ')"
[ "$left" = "exclude " ] \
    && _pass "concurrent: nothing is left beside the exclude file" \
    || _fail "concurrent: left beside the exclude file: $left"
rm -rf "$host" "$outputs"
exit "$ASSERT_FAIL"
