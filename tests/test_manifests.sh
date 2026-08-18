#!/usr/bin/env bash
# L1: the built tree's manifests are valid JSON, carry the install identity
# users are keyed on, and pass `claude plugin validate` at both levels
# (marketplace catalog and plugin).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env MARKETPLACE_TREE PLUGIN_ROOT

CATALOG="$MARKETPLACE_TREE/.claude-plugin/marketplace.json"
PLUGIN_MANIFEST="$PLUGIN_ROOT/.claude-plugin/plugin.json"
HOOKS_MANIFEST="$PLUGIN_ROOT/hooks/hooks.json"

for j in "$CATALOG" "$PLUGIN_MANIFEST" "$HOOKS_MANIFEST"; do
    rel="${j#"$MARKETPLACE_TREE"/}"
    if jq -e . "$j" >/dev/null 2>&1; then
        _pass "valid json: $rel"
    else
        _fail "invalid json: $rel"
    fi
done

# Install identity: these strings are what existing installs are keyed on
# (docs/repository-model.md: "Neither name may change").
[ "$(jq -r '.name // "MISSING"' "$PLUGIN_MANIFEST" 2>/dev/null)" = "llm-wiki" ] \
    && _pass "plugin name is exactly llm-wiki" || _fail "plugin name is not exactly llm-wiki"
[ "$(jq -r '.name // "MISSING"' "$CATALOG" 2>/dev/null)" = "llm-wiki-colab" ] \
    && _pass "catalog name is exactly llm-wiki-colab" || _fail "catalog name is not exactly llm-wiki-colab"
[ "$(jq -r '.plugins[0].source // "MISSING"' "$CATALOG" 2>/dev/null)" = "./claude/plugins/llm-wiki" ] \
    && _pass "catalog plugins[0].source is ./claude/plugins/llm-wiki" \
    || _fail "catalog plugins[0].source is not ./claude/plugins/llm-wiki"

if command -v claude >/dev/null 2>&1; then
    claude plugin validate "$MARKETPLACE_TREE" >/dev/null 2>&1 && _pass "claude plugin validate: marketplace" || _fail "marketplace validate"
    claude plugin validate "$PLUGIN_ROOT" >/dev/null 2>&1 && _pass "claude plugin validate: plugin" || _fail "plugin validate"
else
    echo "  skip  claude plugin validate (CLI not on PATH)"
fi

exit "$ASSERT_FAIL"
