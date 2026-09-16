#!/usr/bin/env bash
# check-harness-auth.test.sh -- canary for the facts scripts/check-harness-auth.sh
# is built on, so a CLI release that changes them is caught here rather than
# as a live run that spends its calls before failing.
#
# For each harness whose CLI is on PATH it checks:
#   1. a credentials file that parses but cannot authenticate makes the check
#      FAIL, name the login command, and exit nonzero (the run spends nothing),
#   2. a missing credentials file does the same without invoking the CLI,
#   3. codex: `login status` still passes a `{}` auth file, the false green
#      that rules it out as the probe (a release that fixes this could make
#      the codex probe free).
# No check here spends a model call; the green path is the script itself
# against real credentials.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CHECK="$HERE/check-harness-auth.sh"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $1"; }

garbage="$(mktemp)"
printf '{}' > "$garbage"
trap 'rm -f "$garbage"' EXIT

for harness in claude codex cursor; do
    binary="$harness"; [ "$harness" = cursor ] && binary=cursor-agent
    if ! command -v "$binary" >/dev/null 2>&1; then
        echo "skip: $binary not on PATH"
        continue
    fi
    var="ISOLATED_$(printf '%s' "$harness" | tr '[:lower:]' '[:upper:]')_AUTH"

    out="$(env "$var=$garbage" "$CHECK" "$harness" </dev/null 2>&1)"; rc=$?
    [ "$rc" -eq 1 ] \
        && ok "$harness: unauthenticated probe exits 1" \
        || bad "$harness: unauthenticated probe exited $rc: $out"
    printf '%s' "$out" | grep -q "^  FAIL $harness .*; run: " \
        && ok "$harness: failure line names the login command" \
        || bad "$harness: failure line lacks the login command: $out"

    out="$(env "$var=$garbage.missing" "$CHECK" "$harness" </dev/null 2>&1)"; rc=$?
    [ "$rc" -eq 1 ] && printf '%s' "$out" | grep -q "no credentials at" \
        && ok "$harness: missing credentials reported without a probe" \
        || bad "$harness: missing credentials: exit $rc: $out"
done

if command -v codex >/dev/null 2>&1; then
    home="$(mktemp -d)"
    cp "$garbage" "$home/auth.json"
    out="$(CODEX_HOME="$home" codex login status </dev/null 2>&1)"; rc=$?
    rm -rf "$home"
    [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "Logged in" \
        && ok "codex: login status still passes a {} auth file (probe must stay a model call)" \
        || bad "codex: login status now rejects a {} auth file (exit $rc); the codex probe could be free"
fi

echo "passed: $PASS  failed: $FAIL"
exit "$FAIL"
