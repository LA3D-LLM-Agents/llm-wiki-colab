#!/usr/bin/env bash
# Ported behavioral test: exercises 20-update-wiki.py's update_wiki fast-forward
# mechanics directly (clean-FF, dirty gate, tracked-edit, divergence, guard),
# from upstream scripts/test/tests/unit/ensure-wiki/update_mechanics_test.py.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

EW="$PLUGIN_ROOT/hooks/session-start.d/20-update-wiki.py"
out="$(python3 "$HERE/mechanics/update_mechanics_test.py" "$EW" 2>&1)"; rc=$?
npass=$(printf '%s' "$out" | grep -c '\[PASS\]')
nfail=$(printf '%s' "$out" | grep -c '\[FAIL\]')
# grep -c alone reports a script that printed nothing as "0 pass, 0 fail" and
# calls that success. The floor is below the current check count so adding
# cases never trips it, but far above zero.
MIN_CHECKS=30
if [ "$rc" -eq 0 ] && [ "$nfail" -eq 0 ] && [ "$npass" -ge "$MIN_CHECKS" ]; then
    _pass "update_wiki fast-forward mechanics: $npass checks pass, 0 fail"
else
    _fail "update_wiki mechanics: $nfail failed, $npass passed (rc=$rc, floor $MIN_CHECKS)"
    printf '%s\n' "$out" | grep '\[FAIL\]' | sed 's/^/    /'
fi

exit "$ASSERT_FAIL"
