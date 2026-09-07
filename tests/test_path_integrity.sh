#!/usr/bin/env bash
# L1: every file the hooks/skills reference via ${CLAUDE_PLUGIN_ROOT}/...
# must be present in the built artifact tree, and the artifact's top level must
# carry the catalog and the repo files the install advertises.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env MARKETPLACE_TREE PLUGIN_ROOT CODEX_PLUGIN_ROOT CURSOR_PLUGIN_ROOT

# Files referenced from the plugin's own hooks/skills.
for f in \
    skills/wiki-init/scripts/init-wiki.sh \
    skills/wiki-init/scripts/init-wiki.py \
    skills/wiki-init/scripts/ensure-local-exclude.py \
    skills/wiki-init/assets/Edge-Types.md.template \
    'skills/wiki-init/assets/SCHEMA_{{REPO_NAME}}.md.template' \
    core/agents/verification-gate.md \
    core/agents/discipline-gates.md \
    core/templates/guidance.md \
    hooks/session-start.d/10-check-attachment.py \
    hooks/session-start.d/15-ensure-local-exclude.py \
    hooks/session-start.d/20-update-wiki.py \
    hooks/session-start.d/30-build-orientation.py \
    hooks/session-start.py \
    hooks/posttooluse.sh \
    hooks/hooks.json \
    .claude-plugin/plugin.json \
    skills/wiki-init/SKILL.md \
    skills/wiki-ask/SKILL.md \
    skills/wiki-ask/scripts/ask.sh \
    skills/wiki-enroll/SKILL.md \
    skills/wiki-enroll/scripts/enroll.sh \
    skills/wiki-lint/SKILL.md \
    skills/wiki-lint/scripts/wiki-reciprocity.py \
    skills/wiki-source/SKILL.md \
    skills/wiki-experiment/SKILL.md; do
    assert_file "$PLUGIN_ROOT/$f" "plugin ships $f"
done

# Artifact top level: the catalog plus the files the README/CITATION reference.
for f in \
    .claude-plugin/marketplace.json \
    README.md \
    LICENSE \
    CITATION.cff; do
    assert_file "$MARKETPLACE_TREE/$f" "artifact ships $f"
done

# The plugin source deliberately carries no catalog; it exists only in output.
assert_no_file "$PLUGIN_ROOT/.claude-plugin/marketplace.json" \
    "no catalog inside the plugin subtree"

# The plugin ships zero commands: every entry point is a skill.
assert_no_file "$PLUGIN_ROOT/commands" \
    "no commands/ directory in the built plugin"

# Standalone skill execution is covered by test_init_states.sh.
assert_no_file "$PLUGIN_ROOT/core/scripts/lib" "plugin omits retired shared library"

# Template hydration: no {{token}} may survive into the shipped README.
assert_not_contains "$(cat "$MARKETPLACE_TREE/README.md" 2>/dev/null)" "{{" \
    "README.md has no unhydrated {{ tokens"

# --- file modes -------------------------------------------------------------
# A hook or skill script that ships without its exec bit is the classic silent
# no-op: the harness runs it, the kernel refuses, and nothing surfaces. Cover
# every subtree, not just the two Cursor adapters test_cursor_manifests.sh names.
#
# Only *.sh is required executable. The shipped *.py under hooks/ are either
# session-start.d stages that the coordinator imports, or targets invoked as
# `python3 <path>`, so they never need the bit; test_hook_targets.sh is what
# demands +x for any hook target that has to exec itself.
for root in "$PLUGIN_ROOT" "$CODEX_PLUGIN_ROOT" "$CURSOR_PLUGIN_ROOT"; do
    subtree="$(basename "$(dirname "$(dirname "$root")")")"
    while IFS= read -r f; do
        if [ -x "$f" ]; then
            _pass "$subtree: executable ${f#"$root/"}"
        else
            _fail "$subtree: not executable ${f#"$root/"}"
        fi
    done < <(find "$root/hooks" "$root/skills" -name '*.sh' -type f | sort)
done

# The three subtrees are assembled from one source, so a file present in all
# three must carry the same mode in all three. Byte-identity parity elsewhere
# does not look at modes, so a per-platform chmod would otherwise pass.
mode_drift=0
while IFS= read -r rel; do
    m_claude="$(stat -c %a "$PLUGIN_ROOT/$rel")"
    for other in "$CODEX_PLUGIN_ROOT" "$CURSOR_PLUGIN_ROOT"; do
        [ -f "$other/$rel" ] || continue
        m_other="$(stat -c %a "$other/$rel")"
        if [ "$m_claude" != "$m_other" ]; then
            _fail "mode drift on $rel: claude $m_claude vs $(basename "$(dirname "$(dirname "$other")")") $m_other"
            mode_drift=1
        fi
    done
done < <(cd "$PLUGIN_ROOT" && find . -type f | sed 's|^\./||' | sort)
[ "$mode_drift" -eq 0 ] && _pass "shared plugin files carry identical modes across the three subtrees"

exit "$ASSERT_FAIL"
