#!/usr/bin/env bash
# L1: the built Codex subtree carries native manifests, the same install
# identity as the Claude subtree, hook wiring rewritten for Codex's tool names,
# and the frontmatter routing phase 2 chose. The gated smoke section proves the
# tree actually installs into a real codex.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env MARKETPLACE_TREE PLUGIN_ROOT CODEX_PLUGIN_ROOT

CODEX_CATALOG="$MARKETPLACE_TREE/.agents/plugins/marketplace.json"
CODEX_MANIFEST="$CODEX_PLUGIN_ROOT/.codex-plugin/plugin.json"
CODEX_HOOKS="$CODEX_PLUGIN_ROOT/hooks/hooks.json"
CLAUDE_MANIFEST="$PLUGIN_ROOT/.claude-plugin/plugin.json"
CLAUDE_HOOKS="$PLUGIN_ROOT/hooks/hooks.json"

for j in "$CODEX_CATALOG" "$CODEX_MANIFEST" "$CODEX_HOOKS"; do
    rel="${j#"$MARKETPLACE_TREE"/}"
    if jq -e . "$j" >/dev/null 2>&1; then
        _pass "valid json: $rel"
    else
        _fail "invalid json: $rel"
    fi
done

# Install identity. These four strings are what an existing Codex install is
# keyed on; docs/repository-model.md: "Neither name may change".
[ "$(jq -r '.name // "MISSING"' "$CODEX_CATALOG" 2>/dev/null)" = "llm-wiki-colab" ] \
    && _pass "codex catalog name is exactly llm-wiki-colab" \
    || _fail "codex catalog name is not exactly llm-wiki-colab"
[ "$(jq -r '.plugins[0].name // "MISSING"' "$CODEX_CATALOG" 2>/dev/null)" = "llm-wiki" ] \
    && _pass "codex catalog lists plugin llm-wiki" \
    || _fail "codex catalog does not list plugin llm-wiki"
[ "$(jq -r '.name // "MISSING"' "$CODEX_MANIFEST" 2>/dev/null)" = "llm-wiki" ] \
    && _pass "codex plugin name is exactly llm-wiki" \
    || _fail "codex plugin name is not exactly llm-wiki"

# Object-form local source pointing at the Codex subtree. The string form Claude
# uses does not resolve here, and the path is what Codex joins onto the fetched
# marketplace root.
[ "$(jq -r '.plugins[0].source.source // "MISSING"' "$CODEX_CATALOG" 2>/dev/null)" = "local" ] \
    && _pass "codex catalog source kind is local" \
    || _fail "codex catalog source kind is not local"
[ "$(jq -r '.plugins[0].source.path // "MISSING"' "$CODEX_CATALOG" 2>/dev/null)" = "./codex/plugins/llm-wiki" ] \
    && _pass "codex catalog source.path is ./codex/plugins/llm-wiki" \
    || _fail "codex catalog source.path is not ./codex/plugins/llm-wiki"

# Codex keys its install cache on the manifest version and nothing else, so a
# version that drifts from the Claude manifest ships an update Codex users never
# receive.
CODEX_VERSION="$(jq -r '.version // "MISSING"' "$CODEX_MANIFEST" 2>/dev/null)"
CLAUDE_VERSION="$(jq -r '.version // "MISSING"' "$CLAUDE_MANIFEST" 2>/dev/null)"
# Anchored ERE rather than a shell glob: a glob would accept 1.2.3-rc1, which
# assemble.py's SEMVER_RE rejects, and the two must agree.
if printf '%s' "$CODEX_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    _pass "codex manifest version is semver ($CODEX_VERSION)"
else
    _fail "codex manifest version is not MAJOR.MINOR.PATCH: $CODEX_VERSION"
fi
[ "$CODEX_VERSION" = "$CLAUDE_VERSION" ] \
    && _pass "both platform manifests carry version $CODEX_VERSION" \
    || _fail "version drift: claude $CLAUDE_VERSION vs codex $CODEX_VERSION"

# Hook wiring. Codex names the patch tool apply_patch; Claude names file writes
# Write|Edit. Asserting both sides catches a transform that rewrote the wrong
# tree as well as one that rewrote neither.
[ "$(jq -r '.hooks.PostToolUse[0].matcher // "MISSING"' "$CODEX_HOOKS" 2>/dev/null)" = "apply_patch" ] \
    && _pass "codex PostToolUse matcher is apply_patch" \
    || _fail "codex PostToolUse matcher is not apply_patch"
[ "$(jq -r '.hooks.PostToolUse[0].matcher // "MISSING"' "$CLAUDE_HOOKS" 2>/dev/null)" = "Write|Edit" ] \
    && _pass "claude PostToolUse matcher is still Write|Edit" \
    || _fail "claude PostToolUse matcher is not Write|Edit"

# SessionStart must be identical in both trees: it is the block the transform
# does not touch, and an untrusted or malformed Codex hooks file fails silently,
# so drift here would never announce itself.
if diff <(jq -S '.hooks.SessionStart' "$CLAUDE_HOOKS" 2>/dev/null) \
        <(jq -S '.hooks.SessionStart' "$CODEX_HOOKS" 2>/dev/null) >/dev/null 2>&1; then
    _pass "SessionStart wiring is identical in both subtrees"
else
    _fail "SessionStart wiring drifted between the Claude and Codex subtrees"
fi

# Drift guard for the transform's blind spot: write_codex_hooks rewrites
# matchers under PostToolUse only, so a Claude tool name added under any other
# event would ship to Codex unrewritten and match nothing. Bash is deliberately
# absent from this list: Codex reports shell calls as tool_name "Bash" too
# (probed), so a Bash matcher is legitimate on both harnesses.
CLAUDE_ONLY_TOOLS='Write|Edit|MultiEdit|NotebookEdit|Glob|Grep|Task|WebFetch|WebSearch'
STRAY="$(jq -r --arg re "$CLAUDE_ONLY_TOOLS" '
    [ .hooks | to_entries[] | .key as $ev | .value[]? | select(has("matcher"))
      | "\($ev):\(.matcher)" ]
    | map(select(test($re))) | join(", ")
' "$CODEX_HOOKS" 2>/dev/null)"
assert_empty "$STRAY" "no Claude-only tool name survives in a codex matcher${STRAY:+ (found: $STRAY)}"
# This jq expression was verified non-vacuous before being written down: it
# returns "" for the emitted codex hooks.json, "PostToolUse:Write|Edit" for the
# Claude one, "PreToolUse:Write|Edit" for a hand-mutated codex file carrying an
# unrewritten PreToolUse block, and "" again when that block's matcher is Bash.

# The Codex tree must carry no Claude manifest: Codex resolves .codex-plugin
# first but falls back to .claude-plugin, and a second stale manifest is exactly
# the silent-divergence trap that fallback creates.
assert_no_file "$CODEX_PLUGIN_ROOT/.claude-plugin" \
    "no .claude-plugin directory in the codex subtree"
STRAY_MANIFESTS="$(find "$CODEX_PLUGIN_ROOT" -name '.claude-plugin' 2>/dev/null)"
assert_empty "$STRAY_MANIFESTS" "no nested .claude-plugin anywhere under the codex subtree${STRAY_MANIFESTS:+ (found: $STRAY_MANIFESTS)}"

# Frontmatter routing, both directions. Codex ignores disable-model-invocation,
# so leaving it in is inert but proves the strip never ran; dropping it from the
# Claude tree would silently make four user-only skills model-invocable.
CODEX_DMI="$(cat "$CODEX_PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | grep -c 'disable-model-invocation')"
CLAUDE_DMI="$(cat "$PLUGIN_ROOT"/skills/*/SKILL.md 2>/dev/null | grep -c 'disable-model-invocation')"
[ "$CODEX_DMI" = "0" ] \
    && _pass "codex skills carry no disable-model-invocation (stripped)" \
    || _fail "codex skills still carry $CODEX_DMI disable-model-invocation lines"
[ "$CLAUDE_DMI" = "4" ] \
    && _pass "claude skills carry exactly 4 disable-model-invocation lines" \
    || _fail "claude skills carry $CLAUDE_DMI disable-model-invocation lines, expected 4"

# Structural parity of the seven skills, and the two universal frontmatter keys
# every harness reads.
for s in wiki-init wiki-doctor wiki-ask wiki-enroll wiki-lint wiki-source wiki-experiment; do
    f="$CODEX_PLUGIN_ROOT/skills/$s/SKILL.md"
    assert_file "$f" "codex subtree ships skill $s"
    assert_grep_file "$f" "name: $s" "codex skill $s declares its name"
    assert_grep_file "$f" "description:" "codex skill $s declares a description"
done
CODEX_SKILLS="$(find "$CODEX_PLUGIN_ROOT/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
[ "$CODEX_SKILLS" = "7" ] \
    && _pass "codex subtree ships exactly 7 skills" \
    || _fail "codex subtree ships $CODEX_SKILLS skills, expected 7"
assert_no_file "$CODEX_PLUGIN_ROOT/commands" "no commands/ directory in the codex subtree"

# The runtime files must be byte-identical across subtrees: one source, two
# emitters, and every difference is supposed to be a manifest or a SKILL.md.
for f in hooks/posttooluse.sh hooks/session-start.sh hooks/ensure-wiki.py core/templates/guidance.md; do
    if cmp -s "$PLUGIN_ROOT/$f" "$CODEX_PLUGIN_ROOT/$f"; then
        _pass "$f is byte-identical in both subtrees"
    else
        _fail "$f differs between the Claude and Codex subtrees"
    fi
done

# ---------------------------------------------------------------------------
# Smoke: the emitted tree installs into a real codex and reaches the model.
# Gated on the CLI being present, exactly like test_manifests.sh's claude gate.
# Needs no authentication and no git repository (both probed): `codex debug
# prompt-input` renders the model-visible prompt locally.
# ---------------------------------------------------------------------------
if command -v codex >/dev/null 2>&1; then
    # A throwaway CODEX_HOME, so the real ~/.codex is never read or written.
    # mktemp lands under $TMPDIR, usually /tmp, where codex prints
    #   "Refusing to create helper binaries under temporary dir"
    # to stderr and proceeds. That warning is benign, which is why every
    # assertion below reads output content rather than exit status or stderr.
    CODEX_SCRATCH="$(mktemp -d 2>/dev/null)"
    CODEX_CWD="$(mktemp -d 2>/dev/null)"
    if [ -z "$CODEX_SCRATCH" ] || [ ! -d "$CODEX_SCRATCH" ] \
       || [ -z "$CODEX_CWD" ] || [ ! -d "$CODEX_CWD" ]; then
        # Never fall through to the user's real CODEX_HOME.
        _fail "could not create a throwaway CODEX_HOME; skipping rather than touching ~/.codex"
        rm -rf "$CODEX_SCRATCH" "$CODEX_CWD"
    else
        trap 'rm -rf "$CODEX_SCRATCH" "$CODEX_CWD"' EXIT INT TERM

        env CODEX_HOME="$CODEX_SCRATCH" codex plugin marketplace add "$MARKETPLACE_TREE" >/dev/null 2>&1
        env CODEX_HOME="$CODEX_SCRATCH" codex plugin add llm-wiki@llm-wiki-colab >/dev/null 2>&1

        # The cache path is the update mechanism: Codex refreshes an install only
        # when this directory name changes, so a version-less or wrongly-keyed
        # cache means users silently keep an old plugin forever.
        assert_file "$CODEX_SCRATCH/plugins/cache/llm-wiki-colab/llm-wiki/$CODEX_VERSION" \
            "codex install cache is keyed on manifest version $CODEX_VERSION"

        # prompt-input renders the exact model-visible prompt, so a skill either
        # appears in it namespaced or the model cannot see it.
        PROMPT_SKILLS="$(cd "$CODEX_CWD" && env CODEX_HOME="$CODEX_SCRATCH" \
            codex debug prompt-input 2>/dev/null | grep -o 'llm-wiki:[a-z-]*' | sort -u)"
        for s in wiki-init wiki-doctor wiki-ask wiki-enroll wiki-lint wiki-source wiki-experiment; do
            assert_contains "$PROMPT_SKILLS" "llm-wiki:$s" \
                "codex prompt-input exposes llm-wiki:$s"
        done

        env CODEX_HOME="$CODEX_SCRATCH" codex plugin remove llm-wiki@llm-wiki-colab >/dev/null 2>&1
        rm -rf "$CODEX_SCRATCH" "$CODEX_CWD"
        trap - EXIT INT TERM
    fi
else
    echo "  skip  codex smoke install (CLI not on PATH)"
fi

exit "$ASSERT_FAIL"
