#!/usr/bin/env bash
# Ported: wiki-reciprocity.py against a fixture wiki with one known one-way link.
# Tested code (core/scripts/wiki-reciprocity.py) and the fixtures are ported
# verbatim from upstream; only this assertion glue is in the plugin's style.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

SCRIPT="$ROOT/core/scripts/wiki-reciprocity.py"
FIX="$HERE/fixtures/reciprocity-wiki"
tmp="$(mktemp -d)"

# Red: shipped fixture has exactly one one-way link (Alpha -> Gamma).
out="$(python3 "$SCRIPT" "$FIX" 2>"$tmp/err")"; rc=$?
[ "$rc" -eq 1 ] && _pass "exits 1 on a reciprocity violation" || _fail "expected exit 1, got $rc"
assert_contains "$out" "Alpha -> Gamma" "reports the one-way Alpha -> Gamma link"
assert_not_contains "$out" "Alpha -> Beta" "reciprocal pair Alpha/Beta not flagged"
grep -qF "1 reciprocity violation" "$tmp/err" && _pass "summary counts one violation" || _fail "summary count wrong"

# Green: add the missing back-reference -> the check clears.
clean="$tmp/wiki"; cp -r "$FIX" "$clean"
printf '\nGamma references [Alpha](Alpha) back.\n' >> "$clean/Gamma.md"
python3 "$SCRIPT" "$clean" >/dev/null 2>&1; rc2=$?
[ "$rc2" -eq 0 ] && _pass "exits 0 when every link is reciprocal" || _fail "expected exit 0, got $rc2"

# Bad path -> usage error (exit 2), not a silent pass.
python3 "$SCRIPT" "$tmp/does-not-exist" >/dev/null 2>&1; rc3=$?
[ "$rc3" -eq 2 ] && _pass "missing wiki dir exits 2" || _fail "expected exit 2, got $rc3"

rm -rf "$tmp"
exit "$ASSERT_FAIL"
