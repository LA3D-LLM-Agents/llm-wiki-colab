#!/usr/bin/env bash
# Smoke test for enroll.sh usage and repository detection.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT
ENROLL="$PLUGIN_ROOT/skills/wiki-enroll/scripts/enroll.sh"

bash "$ENROLL" --help >/dev/null 2>&1 && _pass "--help exits 0" || _fail "--help nonzero"

tmp="$(mktemp -d)"
( cd "$tmp" && bash "$ENROLL" >/dev/null 2>&1 ); [ $? -eq 12 ] \
    && _pass "outside a git repository -> exit 12" \
    || _fail "outside-repository exit not 12"

rm -rf "$tmp"
exit "$ASSERT_FAIL"
