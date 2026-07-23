#!/usr/bin/env bash
# Ported behavioral test: exercises ensure-wiki.py's update_wiki fast-forward
# mechanics directly (clean-FF, dirty gate, tracked-edit, divergence, guard),
# from upstream scripts/test/tests/unit/ensure-wiki/update_mechanics_test.py.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

EW="$ROOT/adapters/claude-code/hooks/ensure-wiki.py"
out="$(python3 "$HERE/mechanics/update_mechanics_test.py" "$EW" 2>&1)"; rc=$?
npass=$(printf '%s' "$out" | grep -c '\[PASS\]')
nfail=$(printf '%s' "$out" | grep -c '\[FAIL\]')
if [ "$rc" -eq 0 ] && [ "$nfail" -eq 0 ]; then
    _pass "update_wiki fast-forward mechanics: $npass checks pass, 0 fail"
else
    _fail "update_wiki mechanics: $nfail failed (rc=$rc)"
    printf '%s\n' "$out" | grep '\[FAIL\]' | sed 's/^/    /'
fi

exit "$ASSERT_FAIL"
