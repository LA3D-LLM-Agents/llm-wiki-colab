#!/usr/bin/env bash
# L1: the built Cursor subtree carries native manifests, the same install
# identity as the other two subtrees, hooks rewritten into Cursor's dialect and
# pointed at the adapter, and the two skill rewrites Cursor's behavior forces
# (frontmatter routing, and a plugin root a skill body can actually resolve).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env MARKETPLACE_TREE PLUGIN_ROOT CURSOR_PLUGIN_ROOT

CURSOR_CATALOG="$MARKETPLACE_TREE/.cursor-plugin/marketplace.json"
CURSOR_MANIFEST="$CURSOR_PLUGIN_ROOT/.cursor-plugin/plugin.json"
CURSOR_HOOKS="$CURSOR_PLUGIN_ROOT/hooks/hooks.json"
CURSOR_ADAPTER="$CURSOR_PLUGIN_ROOT/hooks/cursor-session-start.sh"

for j in "$CURSOR_CATALOG" "$CURSOR_MANIFEST" "$CURSOR_HOOKS"; do
    rel="${j#"$MARKETPLACE_TREE"/}"
    if jq -e . "$j" >/dev/null 2>&1; then
        _pass "valid json: $rel"
    else
        _fail "invalid json: $rel"
    fi
done

# Install identity. Cursor imports Claude-installed plugins and deduplicates on
# marketplaceName/pluginName, so these strings are not merely stable over time,
# they must equal the Claude catalog's or a dual-harness user gets two copies
# whose hooks both fire (docs/repository-model.md).
[ "$(jq -r '.name // "MISSING"' "$CURSOR_CATALOG" 2>/dev/null)" = "llm-wiki-colab" ] \
    && _pass "cursor catalog name is exactly llm-wiki-colab" \
    || _fail "cursor catalog name is not exactly llm-wiki-colab"
[ "$(jq -r '.plugins[0].name // "MISSING"' "$CURSOR_CATALOG" 2>/dev/null)" = "llm-wiki" ] \
    && _pass "cursor catalog lists plugin llm-wiki" \
    || _fail "cursor catalog does not list plugin llm-wiki"
[ "$(jq -r '.name // "MISSING"' "$CURSOR_MANIFEST" 2>/dev/null)" = "llm-wiki" ] \
    && _pass "cursor plugin name is exactly llm-wiki" \
    || _fail "cursor plugin name is not exactly llm-wiki"

# Kebab, no periods: a name carrying a period reads as a path segment in
# Cursor's install layout. Anchored ERE, so a stray dot anywhere fails.
CATALOG_NAME="$(jq -r '.name // ""' "$CURSOR_CATALOG" 2>/dev/null)"
if printf '%s' "$CATALOG_NAME" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*$'; then
    _pass "cursor catalog name is kebab-case with no periods ($CATALOG_NAME)"
else
    _fail "cursor catalog name is not kebab-case-without-periods: $CATALOG_NAME"
fi

# Source is the plain string form pointing at Cursor's own subtree; Codex's
# object form does not resolve here, and Claude's points at claude/.
[ "$(jq -r '.plugins[0].source // "MISSING"' "$CURSOR_CATALOG" 2>/dev/null)" = "./cursor/plugins/llm-wiki" ] \
    && _pass "cursor catalog source is ./cursor/plugins/llm-wiki" \
    || _fail "cursor catalog source is not ./cursor/plugins/llm-wiki"

# Cursor nests the catalog description under metadata, unlike Codex which reads
# interface.displayName. A description at the root would simply not be read.
CURSOR_META_DESC="$(jq -r '.metadata.description // ""' "$CURSOR_CATALOG" 2>/dev/null)"
assert_contains "$CURSOR_META_DESC" "LLM-wiki" "cursor catalog description lives under metadata"
[ "$(jq -r 'has("description")' "$CURSOR_CATALOG" 2>/dev/null)" = "false" ] \
    && _pass "cursor catalog carries no root-level description" \
    || _fail "cursor catalog carries a root-level description Cursor does not read"

# Cursor reads no version, but one build states one number everywhere, so the
# stamp is anchored to the artifact's own VERSION file exactly like Codex's.
CURSOR_VERSION="$(jq -r '.version // "MISSING"' "$CURSOR_MANIFEST" 2>/dev/null)"
TREE_VERSION="$(tr -d '[:space:]' < "$MARKETPLACE_TREE/VERSION" 2>/dev/null)"
[ "$CURSOR_VERSION" = "$TREE_VERSION" ] \
    && _pass "cursor manifest matches the artifact VERSION file ($TREE_VERSION)" \
    || _fail "cursor manifest $CURSOR_VERSION does not match artifact VERSION $TREE_VERSION"

# The Cursor tree must carry no Claude manifest, same reason as the Codex tree:
# Codex's plugin fallback chain ends at .cursor-plugin, so a Claude manifest
# left here is a second stale manifest some future path could silently prefer.
assert_no_file "$CURSOR_PLUGIN_ROOT/.claude-plugin" \
    "no .claude-plugin directory in the cursor subtree"
STRAY_MANIFESTS="$(find "$MARKETPLACE_TREE/cursor" -name '.claude-plugin' 2>/dev/null)"
assert_empty "$STRAY_MANIFESTS" "no nested .claude-plugin anywhere under cursor/${STRAY_MANIFESTS:+ (found: $STRAY_MANIFESTS)}"

# --- hooks: Cursor's dialect, not Claude's ---------------------------------
# Cursor's parser reads lowercase event names and a schema `version`. A
# Claude-dialect file here is not an error Cursor reports; the hook simply never
# fires, so every field is asserted positively.
[ "$(jq -r '.version // "MISSING"' "$CURSOR_HOOKS" 2>/dev/null)" = "1" ] \
    && _pass "cursor hooks.json declares schema version 1" \
    || _fail "cursor hooks.json does not declare version 1"
[ "$(jq -r '.hooks.sessionStart | length' "$CURSOR_HOOKS" 2>/dev/null)" = "1" ] \
    && _pass "cursor hooks.json declares exactly one sessionStart hook" \
    || _fail "cursor hooks.json does not declare exactly one sessionStart hook"
[ "$(jq -r '.hooks.sessionStart[0].type // "MISSING"' "$CURSOR_HOOKS" 2>/dev/null)" = "command" ] \
    && _pass "cursor sessionStart hook is type command" \
    || _fail "cursor sessionStart hook is not type command"

# ${CURSOR_PLUGIN_ROOT} expands in this command string and nowhere else in the
# tree, so its absence here means the adapter is invoked by a path that does not
# exist. It must appear twice: once for the script, once as its argv[1].
CURSOR_CMD="$(jq -r '.hooks.sessionStart[0].command // ""' "$CURSOR_HOOKS" 2>/dev/null)"
assert_contains "$CURSOR_CMD" '${CURSOR_PLUGIN_ROOT}' \
    "cursor sessionStart command expands \${CURSOR_PLUGIN_ROOT}"
assert_contains "$CURSOR_CMD" "hooks/cursor-session-start.sh" \
    "cursor sessionStart command runs the adapter"
CMD_ROOT_REFS="$(printf '%s' "$CURSOR_CMD" | grep -o 'CURSOR_PLUGIN_ROOT' | wc -l | tr -d ' ')"
[ "$CMD_ROOT_REFS" = "2" ] \
    && _pass "cursor sessionStart command passes the plugin root as argv[1] too" \
    || _fail "cursor sessionStart command names CURSOR_PLUGIN_ROOT $CMD_ROOT_REFS times, expected 2"

# No Claude dialect survives. grep is case-sensitive, so this does not match the
# lowercase key the file is supposed to carry.
assert_not_contains "$(cat "$CURSOR_HOOKS" 2>/dev/null)" "SessionStart" \
    "cursor hooks.json carries no Claude-style SessionStart key"
assert_not_contains "$(cat "$CURSOR_HOOKS" 2>/dev/null)" "CLAUDE_PLUGIN_ROOT" \
    "cursor hooks.json carries no \${CLAUDE_PLUGIN_ROOT} reference"

# The adapter itself. Cursor runs the command through bash, but a non-executable
# hook script is the classic silent-no-hook failure, so the mode is asserted.
assert_file "$CURSOR_ADAPTER" "cursor subtree ships hooks/cursor-session-start.sh"
if [ -x "$CURSOR_ADAPTER" ]; then
    _pass "cursor adapter is executable"
else
    _fail "cursor adapter is not executable"
fi

# --- skills ----------------------------------------------------------------
# Structural parity of the seven skills, and the two universal frontmatter keys
# every harness reads.
for s in wiki-init wiki-doctor wiki-ask wiki-enroll wiki-lint wiki-source wiki-experiment; do
    f="$CURSOR_PLUGIN_ROOT/skills/$s/SKILL.md"
    assert_file "$f" "cursor subtree ships skill $s"
    assert_grep_file "$f" "name: $s" "cursor skill $s declares its name"
    assert_grep_file "$f" "description:" "cursor skill $s declares a description"
done
CURSOR_SKILLS="$(find "$CURSOR_PLUGIN_ROOT/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
[ "$CURSOR_SKILLS" = "7" ] \
    && _pass "cursor subtree ships exactly 7 skills" \
    || _fail "cursor subtree ships $CURSOR_SKILLS skills, expected 7"

# Frontmatter routing, both directions. On Cursor the key is not merely inert:
# a skill carrying disable-model-invocation is suppressed entirely, neither
# listed nor invocable (probed by mutation, cursor-agent 2026.08.11). Dropping
# it from the Claude tree would silently make four user-only skills
# model-invocable there, so both counts are asserted.
CURSOR_DMI="$(cat "$CURSOR_PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | grep -c 'disable-model-invocation')"
CLAUDE_DMI="$(cat "$PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | grep -c 'disable-model-invocation')"
[ "$CURSOR_DMI" = "0" ] \
    && _pass "cursor skills carry no disable-model-invocation (stripped)" \
    || _fail "cursor skills still carry $CURSOR_DMI disable-model-invocation lines"
[ "$CLAUDE_DMI" = "4" ] \
    && _pass "claude skills carry exactly 4 disable-model-invocation lines" \
    || _fail "claude skills carry $CLAUDE_DMI disable-model-invocation lines, expected 4"

# Skill bodies. Cursor expands no plugin-root variable in a body and exports
# none into the agent's shell, so a surviving ${CLAUDE_PLUGIN_ROOT} is a command
# that fails with exit 127. The replacement is only usable if the file also says
# what it means, so both halves are asserted.
CURSOR_VAR_REFS="$(grep -l 'CLAUDE_PLUGIN_ROOT' "$CURSOR_PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null)"
assert_empty "$CURSOR_VAR_REFS" "no CLAUDE_PLUGIN_ROOT reference in any cursor skill${CURSOR_VAR_REFS:+ (found: $CURSOR_VAR_REFS)}"
DEFINED="$(grep -l "means this plugin" "$CURSOR_PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
REWRITTEN="$(grep -l '<plugin_root>' "$CURSOR_PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
[ "$REWRITTEN" -gt 0 ] \
    && _pass "$REWRITTEN cursor skills use the <plugin_root> placeholder" \
    || _fail "no cursor skill uses the <plugin_root> placeholder"
[ "$DEFINED" = "$REWRITTEN" ] \
    && _pass "every rewritten cursor skill defines <plugin_root> ($DEFINED)" \
    || _fail "$REWRITTEN cursor skills use <plugin_root> but only $DEFINED define it"
# The Claude subtree keeps the variable: it works there, and rewriting it would
# turn a resolved path into a substitution the model has to perform by hand.
assert_grep_file "$PLUGIN_ROOT/skills/wiki-doctor/SKILL.md" '${CLAUDE_PLUGIN_ROOT}' \
    "claude skill bodies still use \${CLAUDE_PLUGIN_ROOT}"

# --- shared runtime --------------------------------------------------------
# One source, three emitters: every difference between subtrees is supposed to
# be a manifest or a SKILL.md. posttooluse.sh ships here unwired, which is fine,
# but it must not have drifted.
for f in hooks/posttooluse.sh hooks/session-start.sh hooks/ensure-wiki.py; do
    if cmp -s "$PLUGIN_ROOT/$f" "$CURSOR_PLUGIN_ROOT/$f"; then
        _pass "$f is byte-identical in the claude and cursor subtrees"
    else
        _fail "$f differs between the claude and cursor subtrees"
    fi
done
CORE_DIFF="$(diff -r "$PLUGIN_ROOT/core" "$CURSOR_PLUGIN_ROOT/core" 2>&1)"
assert_empty "$CORE_DIFF" "core/ is identical in the claude and cursor subtrees${CORE_DIFF:+ (${CORE_DIFF%%$'\n'*})}"

# --- no symlinks anywhere --------------------------------------------------
# Cursor silently ignores symlinks in an installed plugin, so a link would ship
# as a file that is simply not there. Scoped to the whole artifact rather than
# to cursor/ alone: the emitters share plugin_ignore and shutil.copytree, so a
# link introduced in the source tree would appear in all three subtrees at once.
SYMLINKS="$(find "$MARKETPLACE_TREE" -type l 2>/dev/null)"
assert_empty "$SYMLINKS" "no symlink anywhere in the assembled output${SYMLINKS:+ (found: $SYMLINKS)}"

# --- the doctor, against the real cursor subtree ---------------------------
# test_doctor.sh exercises the dialect branch against a shaped fixture because
# it must pass before this subtree exists. This is the same check against what
# actually ships, invoked the way a Cursor agent would: absolute path, and no
# plugin-root variable in the environment.
d="$(mk_scratch https://github.com/foo/bar.git)"
( cd "$d" && bash "$CURSOR_PLUGIN_ROOT/core/init-wiki.sh" --agent claude-code >/dev/null 2>&1 )
dout="$( cd "$d" && env -u CLAUDE_PLUGIN_ROOT bash "$CURSOR_PLUGIN_ROOT/core/scripts/wiki-doctor.sh" 2>&1 )"
assert_contains "$dout" "cursor dialect"        "doctor reads the emitted cursor subtree as cursor dialect"
assert_contains "$dout" "orientation dry-run emits" "doctor's dry-run reaches orientation through the adapter"
assert_contains "$dout" "structural failures: 0"    "emitted cursor subtree passes the doctor cleanly"
rm -rf "$d"

# Every assertion above was watched fail before it was written down. Against a
# mutated copy of the built tree, one per failure class: a period in the catalog
# name, a renamed plugin manifest, a source pointing at claude/, the description
# moved to the catalog root, a drifted version, a .claude-plugin riding along,
# hooks.json left in Claude dialect, the adapter's argv[1] dropped, the adapter
# non-executable, the adapter deleted, disable-model-invocation restored on a
# cursor skill and stripped from the Claude ones, ${CLAUDE_PLUGIN_ROOT} put back
# in a cursor body, the <plugin_root> definition removed, core/ and
# hooks/session-start.sh drifted, a real file replaced by a symlink, a skill
# deleted, and the hooks schema version removed. Each reddened the assertion it
# targets and no other. The other direction was probed too: rewording a skill
# description and the catalog's plugin blurb, both legitimate in-spec edits,
# leaves all 59 assertions green.

# ---------------------------------------------------------------------------
# Smoke: the emitted tree installs into a real cursor-agent and its sessionStart
# hook reaches the model. Double-gated, unlike the Codex smoke. Codex renders
# its model-visible prompt locally into a throwaway CODEX_HOME; Cursor offers no
# equivalent, so this writes into the user's real ~/.cursor/plugins/local and
# spends a model call. Both are things a plain `tests/run.sh` must not do
# unasked, hence LLM_WIKI_CURSOR_SMOKE=1.
# Minimum cursor-agent is 2026.08.11: earlier builds do not run plugin-shipped
# sessionStart hooks at all.
# ---------------------------------------------------------------------------
if [ "${LLM_WIKI_CURSOR_SMOKE:-}" = "1" ] && command -v cursor-agent >/dev/null 2>&1; then
    LOCAL_PLUGINS="$HOME/.cursor/plugins/local"
    SMOKE_DIR="$LOCAL_PLUGINS/llmwiki-smoke"
    STASH_DIR="$LOCAL_PLUGINS/.llmwiki-smoke-stash"
    # A token that exists nowhere but the fabricated wiki index, so quoting it
    # back cannot come from training, the workspace, or the prompt.
    MARKER="LLMWIKI-SMOKE-A7F3C1"

    SMOKE_FIX="$(mk_scratch https://github.com/foo/smokerepo.git)"
    mkdir -p "$SMOKE_FIX/.llm-wiki"
    git -C "$SMOKE_FIX/.llm-wiki" init -q
    printf '# Index\n\n## Pages\n- [[%s]] - the only page in this wiki\n' "$MARKER" \
        >"$SMOKE_FIX/.llm-wiki/index_smokerepo.md"
    printf '# Log\n\n## [2026-08-25] seeded\nSeeded for the smoke.\n' \
        >"$SMOKE_FIX/.llm-wiki/log_smokerepo.md"

    smoke_cleanup() {
        rm -rf "$SMOKE_DIR"
        [ -d "$STASH_DIR" ] && mv "$STASH_DIR" "$LOCAL_PLUGINS/llm-wiki"
        rm -rf "$SMOKE_FIX"
    }
    trap smoke_cleanup EXIT INT TERM

    # Cursor's skill namespace is flat, so a real llm-wiki install alongside the
    # smoke copy would put two same-named skill sets in front of the model and
    # fire both plugins' hooks. Move it out of the way and put it back.
    [ -d "$LOCAL_PLUGINS/llm-wiki" ] && mv "$LOCAL_PLUGINS/llm-wiki" "$STASH_DIR"

    # Copy, never link: Cursor silently ignores symlinks inside an installed
    # plugin, so a linked tree installs as a plugin with no files in it.
    mkdir -p "$SMOKE_DIR"
    cp -R "$CURSOR_PLUGIN_ROOT/." "$SMOKE_DIR/"

    SMOKE_PROMPT='Answer in exactly two lines and nothing else. Line 1: "SKILLS:" followed by the names of every skill available to you whose name starts with wiki, comma separated, or NONE. Line 2: "MARKER:" followed by the exact token in your context that starts with LLMWIKI-SMOKE-, or NONE. Do not use any tools.'
    SMOKE_OUT="$(cursor-agent -p --trust --workspace "$SMOKE_FIX" "$SMOKE_PROMPT" 2>&1)"

    # Load proof first. If the plugin did not install at all, the marker
    # assertion below would fail too and say nothing about why.
    assert_contains "$SMOKE_OUT" "wiki-doctor" \
        "cursor-agent lists a wiki skill from the installed plugin"
    assert_contains "$SMOKE_OUT" "wiki-init" \
        "cursor-agent lists wiki-init, which carries disable-model-invocation at the source"
    # The marker exists only in the fabricated index the sessionStart hook read,
    # so quoting it back means additional_context reached the model.
    assert_contains "$SMOKE_OUT" "$MARKER" \
        "sessionStart additional_context reached the model (marker quoted back)"

    smoke_cleanup
    trap - EXIT INT TERM
else
    echo "  skip  cursor smoke install (needs LLM_WIKI_CURSOR_SMOKE=1 and cursor-agent on PATH)"
fi

exit "$ASSERT_FAIL"
