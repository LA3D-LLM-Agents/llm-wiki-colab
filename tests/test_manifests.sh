#!/usr/bin/env bash
# L1: the built tree's manifests are valid JSON, carry the install identity
# users are keyed on, and pass `claude plugin validate` at both levels
# (marketplace catalog and plugin).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
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

assert_no_file "$PLUGIN_ROOT/.codex-plugin" "Claude subtree carries no Codex manifest"
assert_no_file "$PLUGIN_ROOT/.cursor-plugin" "Claude subtree carries no Cursor manifest"
assert_no_file "$PLUGIN_ROOT/skills/wiki-doctor" "retired doctor is absent"

# Install identity: these strings are what existing installs are keyed on
# (docs/repository-model.md: "Neither name may change").
[ "$(jq -r '.name // "MISSING"' "$PLUGIN_MANIFEST" 2>/dev/null)" = "llm-wiki" ] \
    && _pass "plugin name is exactly llm-wiki" || _fail "plugin name is not exactly llm-wiki"
[ "$(jq -r '.name // "MISSING"' "$CATALOG" 2>/dev/null)" = "llm-wiki-colab" ] \
    && _pass "catalog name is exactly llm-wiki-colab" || _fail "catalog name is not exactly llm-wiki-colab"
[ "$(jq -r '.plugins[0].source // "MISSING"' "$CATALOG" 2>/dev/null)" = "./claude/plugins/llm-wiki" ] \
    && _pass "catalog plugins[0].source is ./claude/plugins/llm-wiki" \
    || _fail "catalog plugins[0].source is not ./claude/plugins/llm-wiki"

# One VERSION, stamped everywhere. Anchoring to the source file rather than to
# the artifact's own copy is the point: a build that stamped a constant would
# still be self-consistent, and only a comparison against the input catches it.
SRC_VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
TREE_VERSION="$(tr -d '[:space:]' < "$MARKETPLACE_TREE/VERSION" 2>/dev/null)"
[ -n "$SRC_VERSION" ] && [ "$TREE_VERSION" = "$SRC_VERSION" ] \
    && _pass "artifact VERSION matches the repo VERSION ($SRC_VERSION)" \
    || _fail "artifact VERSION '$TREE_VERSION' does not match repo VERSION '$SRC_VERSION'"
[ "$(jq -r '.version // "MISSING"' "$PLUGIN_MANIFEST" 2>/dev/null)" = "$SRC_VERSION" ] \
    && _pass "claude plugin manifest carries $SRC_VERSION" \
    || _fail "claude plugin manifest version is not $SRC_VERSION"
assert_grep_file "$MARKETPLACE_TREE/CITATION.cff" "version: \"$SRC_VERSION\"" \
    "emitted CITATION.cff carries $SRC_VERSION"
assert_grep_file "$MARKETPLACE_TREE/README.md" "Version $SRC_VERSION," \
    "emitted README states the version"

# One description, stamped everywhere. The source manifest carries none, for
# the same reason it carries no version: the build is the only writer, so the
# installed plugin and the catalog entry cannot drift apart, and the three
# harness subtrees describe one product. The expected wording is a reviewed
# literal rather than a read-back of the build's constant, so rewording is a
# deliberate two-place edit.
CLAUDE_DESC="Opt-in per-repo llm-wiki memory for Claude Code: session-start orientation (index + last-5 log) and a verification-gate advisory."
[ "$(jq -r '.description // "MISSING"' "$PLUGIN_MANIFEST" 2>/dev/null)" = "$CLAUDE_DESC" ] \
    && _pass "claude plugin manifest carries the stamped description" \
    || _fail "claude plugin manifest description is not the stamped wording: $(jq -r '.description // "MISSING"' "$PLUGIN_MANIFEST" 2>/dev/null)"
[ "$(jq -r '.plugins[0].description // "MISSING"' "$CATALOG" 2>/dev/null)" = "$CLAUDE_DESC" ] \
    && _pass "claude catalog entry carries the same description" \
    || _fail "claude catalog entry description differs from the plugin manifest"

# The three subtrees differ only in the harness they name.
for pair in "codex:.codex-plugin:Codex" "cursor:.cursor-plugin:Cursor"; do
    IFS=: read -r sub manifest_dir label <<< "$pair"
    other="$(jq -r '.description // "MISSING"' "$MARKETPLACE_TREE/$sub/plugins/llm-wiki/$manifest_dir/plugin.json" 2>/dev/null)"
    [ "${other/for $label:/for Claude Code:}" = "$CLAUDE_DESC" ] \
        && _pass "$sub description matches Claude's up to the harness name" \
        || _fail "$sub description diverges from Claude's: $other"
done

# The build refuses a source manifest that carries its own description, so a
# hand edit cannot reintroduce a second writer. Exercised on a scratch copy of
# the source tree, since assemble.py locates its inputs relative to itself.
scratch="$(mktemp -d)"
cp -R "$ROOT/build" "$ROOT/plugins" "$ROOT/VERSION" "$ROOT/CITATION.cff" "$ROOT/LICENSE" "$scratch/"
rm -rf "$scratch/build/out"
src_manifest="$scratch/plugins/llm-wiki/.claude-plugin/plugin.json"
jq '. + {description: "hand-written"}' "$src_manifest" > "$src_manifest.tmp" && mv "$src_manifest.tmp" "$src_manifest"
if err="$(uv run "$scratch/build/assemble.py" --out "$scratch/out" \
        --owner-repo o/r --source-ref 0000000000000000000000000000000000000000 2>&1 >/dev/null)"; then
    _fail "build accepted a source manifest carrying a description"
else
    assert_contains "$err" "description" "build refuses a source manifest carrying a description"
fi
rm -rf "$scratch"

if command -v claude >/dev/null 2>&1; then
    claude plugin validate "$MARKETPLACE_TREE" >/dev/null 2>&1 && _pass "claude plugin validate: marketplace" || _fail "marketplace validate"
    claude plugin validate "$PLUGIN_ROOT" >/dev/null 2>&1 && _pass "claude plugin validate: plugin" || _fail "plugin validate"
else
    echo "  skip  claude plugin validate (CLI not on PATH)"
fi

exit "$ASSERT_FAIL"
