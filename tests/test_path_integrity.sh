#!/usr/bin/env bash
# L1: every file the hooks/commands/skills reference via ${CLAUDE_PLUGIN_ROOT}/...
# must be present in the built artifact tree, and the artifact's top level must
# carry the catalog and the repo files the install advertises.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env MARKETPLACE_TREE PLUGIN_ROOT

# Files referenced from the plugin's own commands/hooks/skills.
for f in \
    core/init-wiki.sh \
    core/Edge-Types.md.template \
    core/agents/verification-gate.md \
    core/agents/discipline-gates.md \
    core/agents/wiki-write-protocol.md \
    core/scripts/wiki-write-protocol/protocol.sh \
    core/scripts/wiki-doctor.sh \
    core/scripts/wiki-reciprocity.py \
    core/scripts/agent-comms/ask.sh \
    core/scripts/agent-comms/enroll.sh \
    core/scripts/kg/build-graph.sh \
    core/templates/guidance.md \
    hooks/ensure-wiki.py \
    hooks/session-start.sh \
    hooks/posttooluse.sh \
    hooks/hooks.json \
    .claude-plugin/plugin.json \
    commands/wiki-init.md \
    commands/wiki-doctor.md \
    commands/wiki-ask.md \
    commands/wiki-enroll.md \
    commands/wiki-lint.md \
    commands/wiki-source.md \
    commands/wiki-experiment.md \
    skills/wiki-lint/SKILL.md \
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

# Template hydration: no {{token}} may survive into the shipped README.
assert_not_contains "$(cat "$MARKETPLACE_TREE/README.md" 2>/dev/null)" "{{" \
    "README.md has no unhydrated {{ tokens"

exit "$ASSERT_FAIL"
