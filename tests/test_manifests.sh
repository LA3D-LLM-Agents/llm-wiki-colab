#!/usr/bin/env bash
# L1: manifests are valid JSON and pass `claude plugin validate` (when the CLI
# is available; skipped in CI where it usually is not).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

for j in .claude-plugin/marketplace.json \
         adapters/claude-code/.claude-plugin/plugin.json \
         adapters/claude-code/hooks/hooks.json; do
    if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$ROOT/$j" 2>/dev/null; then
        _pass "valid json: $j"
    else
        _fail "invalid json: $j"
    fi
done

if command -v claude >/dev/null 2>&1; then
    claude plugin validate "$ROOT" >/dev/null 2>&1 && _pass "claude plugin validate: marketplace" || _fail "marketplace validate"
    claude plugin validate "$ROOT/adapters/claude-code" >/dev/null 2>&1 && _pass "claude plugin validate: plugin" || _fail "plugin validate"
else
    echo "  skip  claude plugin validate (CLI not on PATH)"
fi

exit "$ASSERT_FAIL"
