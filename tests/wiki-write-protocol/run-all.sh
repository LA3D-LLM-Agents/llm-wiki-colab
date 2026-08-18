#!/usr/bin/env bash
# Run every scenario; report PASS/FAIL count. Exit code = number of failures.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

# The protocol under test ships in the built plugin tree; scenarios resolve it
# through sandbox.sh. Fail loudly here rather than once per scenario.
PROTOCOL_SH="${PLUGIN_ROOT:-}/core/scripts/wiki-write-protocol/protocol.sh"
if [ -z "${PLUGIN_ROOT:-}" ] || [ ! -f "$PROTOCOL_SH" ]; then
    echo "protocol.sh not resolvable from PLUGIN_ROOT='${PLUGIN_ROOT:-<unset>}';" \
         "run via tests/run.sh (it builds the artifact tree and exports it)" >&2
    exit 1
fi

PASS=0
FAIL=0
FAILED=()

for scenario in "$HERE"/scenarios/*/run.sh; do
    name="$(basename "$(dirname "$scenario")")"
    echo "================================================================"
    echo "Running $name"
    echo "================================================================"
    if bash "$scenario"; then
        PASS=$((PASS+1))
    else
        FAIL=$((FAIL+1))
        FAILED+=("$name")
    fi
    echo ""
done

echo "================================================================"
echo "Summary: $PASS passed, $FAIL failed"
if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "Failures:"
    for f in "${FAILED[@]}"; do echo "  - $f"; done
fi
exit "$FAIL"
