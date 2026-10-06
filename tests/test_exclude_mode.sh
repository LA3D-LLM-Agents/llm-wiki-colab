#!/usr/bin/env bash
# L3: the session-start hook rewrites .git/info/exclude through a temporary
# file, which would otherwise take its mode from the umask. The host's mode
# must survive, in both directions: a group-writable file in a shared
# repository must stay writable, and a private file must not become readable.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

# A fresh file under this umask is 644, which neither mode below equals, so a
# rewrite that drops the mode cannot pass by coincidence.
umask 022

for mode in 664 600; do
    host="$(mk_scratch)"
    git init -q "$host/.llm-wiki"
    exclude="$host/.git/info/exclude"
    printf '# personal excludes\n' > "$exclude"
    chmod "$mode" "$exclude"
    if [ "$(stat -c %a "$exclude")" != "$mode" ]; then
        echo "  skip  exclude mode $mode (this filesystem does not keep mode bits)"
        rm -rf "$host"
        continue
    fi

    out="$(cd "$host" && python3 "$PLUGIN_ROOT/hooks/session-start.py" 2>&1 </dev/null)"

    assert_not_contains "$out" "could not ensure the local wiki ignore rule" \
        "mode $mode: hook reports no exclude failure"
    # The rule landing proves the rewrite ran; without it the mode check is vacuous.
    assert_grep_file "$exclude" "/.llm-wiki/" "mode $mode: hook appended the wiki rule"
    after="$(stat -c %a "$exclude")"
    if [ "$after" = "$mode" ]; then
        _pass "mode $mode: exclude keeps its mode across the rewrite"
    else
        _fail "mode $mode: exclude mode became $after"
    fi
    rm -rf "$host"
done
exit "$ASSERT_FAIL"
