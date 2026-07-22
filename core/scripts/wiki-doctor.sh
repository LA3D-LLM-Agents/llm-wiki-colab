#!/usr/bin/env bash
# /wiki-doctor: connectivity self-check for the llm-wiki plugin.
#
# Run from the project root (where .llm-wiki/ lives), with CLAUDE_PLUGIN_ROOT
# set (Claude Code sets it; the command wrapper passes it through). Prints a
# green/red checklist. Exit code = number of failed STRUCTURAL checks. Missing
# KG deps or no network are reported as warnings, not failures, so a clean
# install on an offline machine still exits 0.
set -uo pipefail

PR="${CLAUDE_PLUGIN_ROOT:-}"
FAIL=0
ok()   { echo "  ok    $1"; }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  warn  $1"; }

echo "llm-wiki doctor"

# 1. Plugin root resolves and carries the manifest.
if [ -n "$PR" ] && [ -f "$PR/.claude-plugin/plugin.json" ]; then
    ok "plugin root resolves ($PR)"
else
    bad "CLAUDE_PLUGIN_ROOT unset or missing .claude-plugin/plugin.json (value: '${PR:-unset}')"
fi

# 2. Gate files shipped.
missing=""
for g in verification-gate discipline-gates wiki-write-protocol; do
    [ -f "$PR/core/agents/$g.md" ] || missing="$missing $g"
done
[ -z "$missing" ] && ok "gate files present (core/agents/)" || bad "missing gate file(s):$missing"

# 3. Hooks declared.
if [ -f "$PR/hooks/hooks.json" ] && grep -q SessionStart "$PR/hooks/hooks.json" && grep -q PostToolUse "$PR/hooks/hooks.json"; then
    ok "hooks.json declares SessionStart + PostToolUse"
else
    bad "hooks.json missing or does not declare both hooks"
fi

# 4. Wiki attached (opt-in): .llm-wiki/ is its own git repo.
if [ -d .llm-wiki ] && git -C .llm-wiki rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    wremote="$(git -C .llm-wiki remote get-url origin 2>/dev/null || echo '(none)')"
    ok "wiki attached at .llm-wiki/ (remote: $wremote)"
    morigin="$(git remote get-url origin 2>/dev/null || echo '')"
    if [ -n "$morigin" ]; then
        expect="${morigin%.git}.wiki.git"
        [ "$wremote" = "$expect" ] || warn "wiki remote is not <origin>.wiki.git (expected $expect)"
    fi
    [ -z "$(git -C .llm-wiki status --porcelain 2>/dev/null)" ] || warn "wiki has uncommitted changes"
else
    bad ".llm-wiki/ absent or not a git repo — run /wiki-init to attach"
fi

# 5. KG deps (optional).
if python3 -c "import rdflib, pyshacl, yaml" >/dev/null 2>&1; then
    if [ -x "$PR/core/scripts/kg/build-graph.sh" ]; then
        ok "KG deps present; build-graph.sh executable"
    else
        warn "KG deps present but build-graph.sh is not executable"
    fi
else
    warn "KG deps (rdflib/pyshacl/pyyaml) not importable — KG build unavailable (optional)"
fi

# 6. Remote reachable + push-ready (no real push; wiki_push has no dry-run).
if [ -d .llm-wiki ]; then
    if git -C .llm-wiki ls-remote >/dev/null 2>&1; then
        if [ -z "$(git -C .llm-wiki status --porcelain 2>/dev/null)" ]; then
            ok "wiki remote reachable; working tree clean (push-ready)"
        else
            warn "wiki remote reachable but working tree is dirty"
        fi
    else
        warn "wiki remote not reachable (offline, no remote, or auth needed)"
    fi
fi

# 7. Orientation dry-run: what SessionStart would inject.
if [ -f "$PR/hooks/session-start.sh" ]; then
    orient="$(bash "$PR/hooks/session-start.sh" 2>/dev/null || true)"
    if printf '%s' "$orient" | grep -q "durable memory"; then
        ok "orientation dry-run emits the session-start reminder"
        tail="$(printf '%s\n' "$orient" | awk '/last 5 log entries/{f=1} f' | grep '^## \[' | tail -1)"
        [ -n "$tail" ] && echo "        last log entry it would surface: $tail"
    else
        warn "session-start produced no orientation (is .llm-wiki attached and scaffolded?)"
    fi
else
    bad "hooks/session-start.sh missing"
fi

echo ""
echo "structural failures: $FAIL"
exit "$FAIL"
