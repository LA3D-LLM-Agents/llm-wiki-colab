#!/usr/bin/env bash
# L1: every core file the hooks/commands/skills reference via
# ${CLAUDE_PLUGIN_ROOT}/... must be present in the assembled adapter
# (run.sh runs package.sh first to copy core/ in).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

A="$ROOT/adapters/claude-code"
for f in \
    core/init-wiki.sh \
    core/agents/verification-gate.md \
    core/agents/discipline-gates.md \
    core/agents/wiki-write-protocol.md \
    core/scripts/wiki-write-protocol/protocol.sh \
    core/scripts/wiki-doctor.sh \
    core/scripts/kg/build-graph.sh \
    core/templates/guidance.md \
    hooks/ensure-wiki.py \
    hooks/session-start.sh \
    hooks/posttooluse.sh \
    hooks/hooks.json \
    .claude-plugin/plugin.json \
    commands/wiki-init.md \
    commands/wiki-doctor.md; do
    assert_file "$A/$f" "plugin ships $f"
done

exit "$ASSERT_FAIL"
