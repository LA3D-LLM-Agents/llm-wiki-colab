#!/usr/bin/env bash
# Minimal assertion helpers for the plugin test suite. Each test sources this,
# runs asserts, and ends with `exit "$ASSERT_FAIL"`. The runner (run.sh)
# aggregates results by exit code.

ASSERT_PASS=0
ASSERT_FAIL=0

_pass() { ASSERT_PASS=$((ASSERT_PASS + 1)); echo "  ok   $1"; }
_fail() { ASSERT_FAIL=$((ASSERT_FAIL + 1)); echo "  FAIL $1"; }

assert_file()    { if [ -e "$1" ]; then _pass "exists: ${2:-$1}"; else _fail "missing: ${2:-$1}"; fi; }
assert_no_file() { if [ -e "$1" ]; then _fail "should not exist: ${2:-$1}"; else _pass "absent: ${2:-$1}"; fi; }
assert_contains()     { if printf '%s' "$1" | grep -qF -- "$2"; then _pass "${3:-contains '$2'}"; else _fail "${3:-missing '$2'}"; fi; }
assert_not_contains() { if printf '%s' "$1" | grep -qF -- "$2"; then _fail "${3:-should omit '$2'}"; else _pass "${3:-omits '$2'}"; fi; }
assert_empty()   { if [ -z "$1" ]; then _pass "${2:-empty output}"; else _fail "${2:-expected empty, got: ${1:0:60}}"; fi; }
assert_grep_file(){ if grep -qF -- "$2" "$1" 2>/dev/null; then _pass "${3:-'$2' in $(basename "$1")}"; else _fail "${3:-'$2' not in $(basename "$1")}"; fi; }

# mk_scratch [origin-url] -> echoes a fresh git repo dir with identity set.
mk_scratch() {
    local d
    d="$(mktemp -d)"
    d="$(cd "$d" && pwd -P)"
    git -C "$d" init -q
    git -C "$d" config user.name "Test User"
    git -C "$d" config user.email "test@example.com"
    [ -n "${1:-}" ] && git -C "$d" remote add origin "$1"
    echo "$d"
}
