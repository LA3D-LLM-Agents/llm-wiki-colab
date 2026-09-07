#!/usr/bin/env bash
# L1: the built Cursor subtree carries native manifests, the same install
# identity as the other two subtrees, hooks rewritten into Cursor's dialect and
# pointed at the adapters, the frontmatter routing Cursor's behavior forces,
# and skill bodies that are byte-identical to the Claude subtree's.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env MARKETPLACE_TREE PLUGIN_ROOT CURSOR_PLUGIN_ROOT

CURSOR_CATALOG="$MARKETPLACE_TREE/.cursor-plugin/marketplace.json"
CURSOR_MANIFEST="$CURSOR_PLUGIN_ROOT/.cursor-plugin/plugin.json"
CURSOR_HOOKS="$CURSOR_PLUGIN_ROOT/hooks/hooks.json"
CURSOR_ADAPTER="$CURSOR_PLUGIN_ROOT/hooks/cursor-session-start.sh"
CURSOR_PRETOOL="$CURSOR_PLUGIN_ROOT/hooks/cursor-pre-tool-use.sh"

# Everything below the closing frontmatter fence of a SKILL.md.
skill_body() { awk 'f; /^---$/ && ++c == 2 { f = 1 }' "$1"; }

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

# preToolUse, matched to Shell. This is the only channel that reaches the shell
# the agent runs a skill's commands in: sessionStart's `env` propagates to later
# hook processes and not to that shell, so without this entry every skill body
# that shells out through ${CLAUDE_PLUGIN_ROOT} fails with exit 127.
[ "$(jq -r '.hooks.preToolUse | length' "$CURSOR_HOOKS" 2>/dev/null)" = "1" ] \
    && _pass "cursor hooks.json declares exactly one preToolUse hook" \
    || _fail "cursor hooks.json does not declare exactly one preToolUse hook"
[ "$(jq -r '.hooks.preToolUse[0].type // "MISSING"' "$CURSOR_HOOKS" 2>/dev/null)" = "command" ] \
    && _pass "cursor preToolUse hook is type command" \
    || _fail "cursor preToolUse hook is not type command"
# Unmatched, the hook would fire for Read, Write, Grep, Task and every MCP tool
# and rewrite input it has no business touching.
[ "$(jq -r '.hooks.preToolUse[0].matcher // "MISSING"' "$CURSOR_HOOKS" 2>/dev/null)" = "Shell" ] \
    && _pass "cursor preToolUse hook is matched to Shell" \
    || _fail "cursor preToolUse hook is not matched to Shell"
PRETOOL_CMD="$(jq -r '.hooks.preToolUse[0].command // ""' "$CURSOR_HOOKS" 2>/dev/null)"
assert_contains "$PRETOOL_CMD" '${CURSOR_PLUGIN_ROOT}' \
    "cursor preToolUse command expands \${CURSOR_PLUGIN_ROOT}"
assert_contains "$PRETOOL_CMD" "hooks/cursor-pre-tool-use.sh" \
    "cursor preToolUse command runs the pre-tool-use adapter"
PRETOOL_ROOT_REFS="$(printf '%s' "$PRETOOL_CMD" | grep -o 'CURSOR_PLUGIN_ROOT' | wc -l | tr -d ' ')"
[ "$PRETOOL_ROOT_REFS" = "2" ] \
    && _pass "cursor preToolUse command passes the plugin root as argv[1] too" \
    || _fail "cursor preToolUse command names CURSOR_PLUGIN_ROOT $PRETOOL_ROOT_REFS times, expected 2"

# The adapters themselves. Cursor runs the command through bash, but a
# non-executable hook script is the classic silent-no-hook failure, so the mode
# is asserted.
assert_file "$CURSOR_ADAPTER" "cursor subtree ships hooks/cursor-session-start.sh"
if [ -x "$CURSOR_ADAPTER" ]; then
    _pass "cursor adapter is executable"
else
    _fail "cursor adapter is not executable"
fi
assert_file "$CURSOR_PRETOOL" "cursor subtree ships hooks/cursor-pre-tool-use.sh"
if [ -x "$CURSOR_PRETOOL" ]; then
    _pass "cursor pre-tool-use adapter is executable"
else
    _fail "cursor pre-tool-use adapter is not executable"
fi

# --- the pre-tool-use adapter, driven directly ------------------------------
# A fabricated preToolUse payload through the emitted script, so the rewrite is
# checked against the file that ships rather than against the template.
PRETOOL_IN='{"tool_name":"Shell","tool_input":{"command":"bash \"${CLAUDE_PLUGIN_ROOT}/tests/root-probe.sh\"","working_directory":"/project"},"tool_use_id":"t1","hook_event_name":"preToolUse"}'
PRETOOL_OUT="$(printf '%s' "$PRETOOL_IN" | bash "$CURSOR_PRETOOL" "$CURSOR_PLUGIN_ROOT" 2>/dev/null)"
[ "$(printf '%s' "$PRETOOL_OUT" | jq -r '.permission // "MISSING"' 2>/dev/null)" = "allow" ] \
    && _pass "pre-tool-use adapter allows a Shell command" \
    || _fail "pre-tool-use adapter does not allow a Shell command"
REWRITTEN_CMD="$(printf '%s' "$PRETOOL_OUT" | jq -r '.updated_input.command // ""' 2>/dev/null)"
# Anchored: the export has to come first, or the original command has already
# run by the time the variable exists.
assert_contains "$REWRITTEN_CMD" "export CLAUDE_PLUGIN_ROOT=$CURSOR_PLUGIN_ROOT; bash" \
    "rewritten command exports the real plugin root before the original command"
[ "$REWRITTEN_CMD" = "export CLAUDE_PLUGIN_ROOT=$CURSOR_PLUGIN_ROOT; bash \"\${CLAUDE_PLUGIN_ROOT}/tests/root-probe.sh\"" ] \
    && _pass "rewritten command preserves the original command byte-for-byte after the prefix" \
    || _fail "rewritten command mangled the original command: $REWRITTEN_CMD"
# tool_input is replaced wholesale, not merged, so a dropped field is a lost
# working directory rather than a visible error.
[ "$(printf '%s' "$PRETOOL_OUT" | jq -r '.updated_input.working_directory // "MISSING"' 2>/dev/null)" = "/project" ] \
    && _pass "pre-tool-use adapter carries other tool_input fields through unchanged" \
    || _fail "pre-tool-use adapter dropped tool_input.working_directory"

# A non-Shell tool must pass through untouched. The payload carries a `command`
# of its own on purpose: an MCP tool taking a command parameter is the case that
# distinguishes a real tool_name guard from an adapter that rewrites whatever
# looks like a command, and a shell prefix injected into an MCP call is not a
# no-op there.
PRETOOL_READ="$(printf '%s' '{"tool_name":"MCP:deploy","tool_input":{"command":"deploy prod"},"hook_event_name":"preToolUse"}' \
    | bash "$CURSOR_PRETOOL" "$CURSOR_PLUGIN_ROOT" 2>/dev/null)"
[ "$(printf '%s' "$PRETOOL_READ" | jq -r '.permission // "MISSING"' 2>/dev/null)" = "allow" ] \
    && _pass "pre-tool-use adapter allows a non-Shell tool" \
    || _fail "pre-tool-use adapter does not allow a non-Shell tool"
[ "$(printf '%s' "$PRETOOL_READ" | jq -r 'has("updated_input")' 2>/dev/null)" = "false" ] \
    && _pass "pre-tool-use adapter emits no updated_input for a non-Shell tool" \
    || _fail "pre-tool-use adapter rewrote the input of a non-Shell tool"

# Fail open, both ways. An unparseable payload and a missing plugin root are the
# two failure modes that would otherwise wedge every shell command in a session.
PRETOOL_JUNK="$(printf 'not json at all' | bash "$CURSOR_PRETOOL" "$CURSOR_PLUGIN_ROOT" 2>/dev/null)"
[ "$(printf '%s' "$PRETOOL_JUNK" | jq -r '.permission // "MISSING"' 2>/dev/null)" = "allow" ] \
    && _pass "pre-tool-use adapter fails open on an unparseable payload" \
    || _fail "pre-tool-use adapter does not fail open on an unparseable payload"
printf '%s' "$PRETOOL_IN" | env -u CLAUDE_PLUGIN_ROOT -u CURSOR_PLUGIN_ROOT bash "$CURSOR_PRETOOL" >/dev/null 2>&1
[ "$?" = "0" ] \
    && _pass "pre-tool-use adapter exits 0 with no plugin root anywhere" \
    || _fail "pre-tool-use adapter exits non-zero with no plugin root, which Cursor reads as a block"

# --- skills ----------------------------------------------------------------
# Structural parity of the six skills, and the two universal frontmatter keys
# every harness reads.
for s in wiki-init wiki-ask wiki-enroll wiki-lint wiki-source wiki-experiment; do
    f="$CURSOR_PLUGIN_ROOT/skills/$s/SKILL.md"
    assert_file "$f" "cursor subtree ships skill $s"
    assert_grep_file "$f" "name: $s" "cursor skill $s declares its name"
    assert_grep_file "$f" "description:" "cursor skill $s declares a description"
done
CURSOR_SKILLS="$(find "$CURSOR_PLUGIN_ROOT/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
[ "$CURSOR_SKILLS" = "6" ] \
    && _pass "cursor subtree ships exactly 6 skills" \
    || _fail "cursor subtree ships $CURSOR_SKILLS skills, expected 6"

# Frontmatter routing, both directions. On Cursor the key is not merely inert:
# a skill carrying disable-model-invocation is suppressed entirely, neither
# listed nor invocable (probed by mutation, cursor-agent 2026.08.11). Dropping
# it from the Claude tree would silently make three user-only skills
# model-invocable there, so both counts are asserted.
CURSOR_DMI="$(cat "$CURSOR_PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | grep -c 'disable-model-invocation')"
CLAUDE_DMI="$(cat "$PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | grep -c 'disable-model-invocation')"
[ "$CURSOR_DMI" = "0" ] \
    && _pass "cursor skills carry no disable-model-invocation (stripped)" \
    || _fail "cursor skills still carry $CURSOR_DMI disable-model-invocation lines"
[ "$CLAUDE_DMI" = "3" ] \
    && _pass "claude skills carry exactly 3 disable-model-invocation lines" \
    || _fail "claude skills carry $CLAUDE_DMI disable-model-invocation lines, expected 3"

# Skill bodies. Frontmatter is routed per harness, but everything below the
# closing fence is one text with one meaning, and the preToolUse hook puts
# CLAUDE_PLUGIN_ROOT into the agent's shell so a body that shells out through
# the variable resolves on Cursor exactly as it does on Claude. Byte identity is
# the assertion: any per-harness wording is prose that has to be maintained
# twice and can only drift.
for s in wiki-init wiki-ask wiki-enroll wiki-lint wiki-source wiki-experiment; do
    if cmp -s <(skill_body "$CURSOR_PLUGIN_ROOT/skills/$s/SKILL.md") \
              <(skill_body "$PLUGIN_ROOT/skills/$s/SKILL.md"); then
        _pass "cursor skill $s body is byte-identical to the claude subtree's"
    else
        _fail "cursor skill $s body differs from the claude subtree's"
    fi
done
# --- shared runtime --------------------------------------------------------
# The shared hooks remain identical; adapters translate the harness protocols.
for f in hooks/posttooluse.sh hooks/session-start.py hooks/session-start.d/10-check-attachment.py hooks/session-start.d/15-ensure-local-exclude.py hooks/session-start.d/20-update-wiki.py hooks/session-start.d/30-build-orientation.py; do
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

# Every assertion above was watched fail before it was written down. Against a
# mutated copy of the built tree, one per failure class: a period in the catalog
# name, a renamed plugin manifest, a source pointing at claude/, the description
# moved to the catalog root, a drifted version, a .claude-plugin riding along,
# hooks.json left in Claude dialect, either adapter's argv[1] dropped, an
# adapter non-executable, an adapter deleted, disable-model-invocation restored
# on a cursor skill and stripped from the Claude ones, core/ and
# hooks/session-start.py drifted, a real file replaced by a symlink, a skill
# deleted, and the hooks schema version removed.
# The preToolUse half was reddened the same way: the matcher dropped, the whole
# entry deleted, the command pointed at the sessionStart script, the script
# deleted and left non-executable, the adapter emitting the original command
# unprefixed, appending the export after the command instead of before, dropping
# the other tool_input fields, rewriting every tool rather than Shell only,
# denying instead of allowing, exiting 1 with no plugin root, emitting nothing at
# all, and the <plugin_root> body substitution put back on one skill. Each
# reddened the assertion it targets and no other.
# The non-Shell probe carries a `command` of its own because of one of those
# runs: with a payload that had none, dropping the adapter's tool_name guard
# entirely left every assertion green.
# The other direction was probed too: rewording a skill description and the
# catalog's plugin blurb, both legitimate in-spec edits, leaves all 80
# assertions green.

# ---------------------------------------------------------------------------
# Smoke: the emitted tree installs into a real cursor-agent and its sessionStart
# hook reaches the model. Double-gated, unlike the Codex smoke. Codex renders
# its model-visible prompt locally into a throwaway CODEX_HOME; Cursor offers no
# equivalent, so this writes into the user's real ~/.cursor/plugins/local and
# spends two model calls, one per delivery mechanism. Both are things a plain
# `tests/run.sh` must not do unasked, hence LLM_WIKI_CURSOR_SMOKE=1.
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
    assert_contains "$SMOKE_OUT" "wiki-lint" \
        "cursor-agent lists a wiki skill from the installed plugin"
    assert_contains "$SMOKE_OUT" "wiki-init" \
        "cursor-agent lists wiki-init, which carries disable-model-invocation at the source"
    # The marker exists only in the fabricated index the sessionStart hook read,
    # so quoting it back means additional_context reached the model.
    assert_contains "$SMOKE_OUT" "$MARKER" \
        "sessionStart additional_context reached the model (marker quoted back)"

    # --- the preToolUse export, end to end ---------------------------------
    # The assertions above prove sessionStart reaches the model. This one proves
    # the plugin root reaches the shell the model runs a skill's commands in,
    # which is a different process and a different mechanism.
    #
    # Test-only probe: verify the export in the actual agent shell.
    mkdir -p "$SMOKE_DIR/tests"
    cat > "$SMOKE_DIR/tests/root-probe.sh" <<'PROBE'
#!/usr/bin/env bash
test -f "$CLAUDE_PLUGIN_ROOT/.cursor-plugin/plugin.json" || exit 1
printf 'ROOT-PROBE from CLAUDE_PLUGIN_ROOT\n'
PROBE
    PROBE_PROMPT='Run exactly: bash "${CLAUDE_PLUGIN_ROOT}/tests/root-probe.sh". Do not substitute the variable, add environment assignments, or use fallbacks. Report its output verbatim.'
    # stdout only: the trace has to stay parseable JSONL for jq.
    PROBE_TRACE="$(cursor-agent -p --trust --force --workspace "$SMOKE_FIX" \
        --output-format stream-json "$PROBE_PROMPT" 2>/dev/null)"
    # `success` and `failure` are two shapes of the same record; taking both
    # means a 127 arrives as a reported exit code and a message rather than as
    # an empty variable that fails every assertion for no stated reason.
    PROBE_CALL="$(printf '%s' "$PROBE_TRACE" \
        | jq -c 'select(.type == "tool_call" and .subtype == "completed")
                 | .tool_call.shellToolCall.result
                 | (.success // .failure)
                 | select(. != null) | select(.command | contains("root-probe"))' \
          2>/dev/null | head -1)"
    PROBE_CMD="$(printf '%s' "$PROBE_CALL" | jq -r '.command // ""' 2>/dev/null)"
    PROBE_RC="$(printf '%s' "$PROBE_CALL" | jq -r '.exitCode // "MISSING"' 2>/dev/null)"
    PROBE_STDOUT="$(printf '%s' "$PROBE_CALL" | jq -r '.stdout // ""' 2>/dev/null)"
    PROBE_BOTH="$(printf '%s' "$PROBE_CALL" | jq -r '(.stdout // "") + (.stderr // "")' 2>/dev/null)"

    # The command as the agent submitted it. A successful shell call is recorded
    # pre-rewrite, so the export prefix itself is not visible here (it shows up
    # only in a `rejected` record, which reports what would have run). What is
    # visible is stronger anyway: the variable reaches the shell unexpanded, so
    # the run below can only work if something set it.
    assert_contains "$PROBE_CMD" '${CLAUDE_PLUGIN_ROOT}/tests/root-probe.sh' \
        "the agent ran the probe command with the variable unexpanded"
    assert_not_contains "$PROBE_CMD" 'CLAUDE_PLUGIN_ROOT=' \
        "the agent set no plugin root of its own in the command"

    # Without the export this is exit 127 on bash "/tests/root-probe.sh".
    [ "$PROBE_RC" = "0" ] \
        && _pass "root probe exited 0 in the agent's shell" \
        || _fail "root probe exited $PROBE_RC in the agent's shell (127 = the plugin root never arrived)"
    # stderr as well as stdout: an unresolved root reports itself as
    # `bash: /tests/root-probe.sh: No such file or directory`, on stderr.
    assert_not_contains "$PROBE_BOTH" "No such file" \
        "root probe's output carries no missing-file error"
    assert_contains "$PROBE_STDOUT" "from CLAUDE_PLUGIN_ROOT" \
        "root probe resolved its root from the exported variable, not its own location"

    smoke_cleanup
    trap - EXIT INT TERM
else
    echo "  skip  cursor smoke install (needs LLM_WIKI_CURSOR_SMOKE=1 and cursor-agent on PATH)"
fi

exit "$ASSERT_FAIL"
