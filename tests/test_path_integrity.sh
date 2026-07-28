#!/usr/bin/env bash
# L1: every core file the hooks/commands/skills reference via
# ${CLAUDE_PLUGIN_ROOT} / ${CURSOR_PLUGIN_ROOT} must be present in the
# assembled adapters (run.sh runs package.sh first to copy core/ in).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

# Shared paths both adapters must ship.
COMMON_CORE=(
    core/init-wiki.sh
    core/agents/verification-gate.md
    core/agents/discipline-gates.md
    core/agents/wiki-write-protocol.md
    core/scripts/wiki-write-protocol/protocol.sh
    core/scripts/wiki-doctor.sh
    core/scripts/wiki-reciprocity.py
    core/scripts/agent-comms/ask.sh
    core/scripts/agent-comms/enroll.sh
    core/scripts/kg/build-graph.sh
    core/templates/guidance.md
    hooks/ensure-wiki.py
    hooks/session-start.sh
    hooks/posttooluse.sh
    hooks/hooks.json
    commands/wiki-init.md
    commands/wiki-doctor.md
    commands/wiki-ask.md
    commands/wiki-enroll.md
)

A="$ROOT/adapters/claude-code"
for f in "${COMMON_CORE[@]}" .claude-plugin/plugin.json; do
    assert_file "$A/$f" "claude plugin ships $f"
done

C="$ROOT/adapters/cursor"
for f in "${COMMON_CORE[@]}" \
    .cursor-plugin/plugin.json \
    hooks/ensure-wiki.sh \
    rules/wiki-as-memory.mdc \
    skills/wiki-experiment/SKILL.md \
    skills/wiki-source/SKILL.md \
    skills/wiki-lint/SKILL.md; do
    assert_file "$C/$f" "cursor plugin ships $f"
done

# Cursor commands/skills must reference CURSOR_PLUGIN_ROOT, not CLAUDE_PLUGIN_ROOT.
if grep -rq 'CLAUDE_PLUGIN_ROOT' "$C/commands" "$C/skills" 2>/dev/null; then
    _fail "cursor adapter still references CLAUDE_PLUGIN_ROOT"
else
    _pass "cursor adapter has no CLAUDE_PLUGIN_ROOT refs"
fi
if grep -rq '\${CURSOR_PLUGIN_ROOT}' "$C/commands" "$C/skills" 2>/dev/null; then
    _pass "cursor adapter references CURSOR_PLUGIN_ROOT"
else
    _fail "cursor adapter missing CURSOR_PLUGIN_ROOT refs"
fi

exit "$ASSERT_FAIL"
