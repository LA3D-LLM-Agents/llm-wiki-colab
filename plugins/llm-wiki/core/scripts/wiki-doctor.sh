#!/usr/bin/env bash
# /wiki-doctor: connectivity self-check for the llm-wiki plugin.
#
# Run from the project root (where .llm-wiki/ lives), with CLAUDE_PLUGIN_ROOT
# set (Claude Code sets it; the command wrapper passes it through). Prints a
# green/red checklist. Exit code = number of failed STRUCTURAL checks. Missing
# KG deps or no network are reported as warnings, not failures, so a clean
# install on an offline machine still exits 0.
set -uo pipefail

# Where the plugin lives. Claude Code exports CLAUDE_PLUGIN_ROOT into the shell
# that runs a skill's commands, and on Cursor the plugin's preToolUse hook
# exports it onto the command. The fallback is the script's own location, two
# levels up from core/scripts/, which keeps the doctor able to report on an
# install where neither of those happened.
PR="${CLAUDE_PLUGIN_ROOT:-}"
PR_SRC="CLAUDE_PLUGIN_ROOT"
if [ -z "$PR" ]; then
    PR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)"
    PR_SRC="script location"
fi
FAIL=0
ok()   { echo "  ok    $1"; }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  warn  $1"; }

echo "llm-wiki doctor"

# 0. Which harness's tree is this? One source emits three subtrees and this
# script is copied byte-identical into all of them, so the tree has to say which
# dialect it is. Each subtree carries exactly one manifest directory (every
# emitter deletes the foreign ones), which makes the manifest that is present
# the dialect marker.
DIALECT=""
MANIFEST=""
if [ -n "$PR" ]; then
    for d in claude codex cursor; do
        if [ -f "$PR/.$d-plugin/plugin.json" ]; then
            DIALECT="$d"
            MANIFEST=".$d-plugin/plugin.json"
            break
        fi
    done
fi

# 1. Plugin root resolves and carries the manifest.
if [ -n "$DIALECT" ]; then
    ok "plugin root resolves ($PR, $DIALECT dialect via $MANIFEST, from $PR_SRC)"
else
    bad "plugin root carries no .claude-plugin/, .codex-plugin/, or .cursor-plugin/ plugin.json (value: '${PR:-unset}', from $PR_SRC)"
fi

# 2. Gate files shipped.
missing=""
for g in verification-gate discipline-gates; do
    [ -f "$PR/core/agents/$g.md" ] || missing="$missing $g"
done
[ -z "$missing" ] && ok "gate files present (core/agents/)" || bad "missing gate file(s):$missing"

# 3. Hooks declared, in this harness's dialect. Claude and Codex read the same
# Claude-dialect file (only the PostToolUse matcher differs between them).
# Cursor reads a native-dialect file: lowercase `sessionStart`, driven through
# an adapter, and no PostToolUse advisory at all, so demanding one there would
# report a failure the tree is not supposed to have.
HOOKS_FILE="$PR/hooks/hooks.json"
if [ "$DIALECT" = "cursor" ]; then
    if [ -f "$HOOKS_FILE" ] && grep -q sessionStart "$HOOKS_FILE"; then
        ok "hooks.json declares sessionStart"
    else
        bad "hooks.json missing or does not declare sessionStart"
    fi
else
    if [ -f "$HOOKS_FILE" ] && grep -q SessionStart "$HOOKS_FILE" && grep -q PostToolUse "$HOOKS_FILE"; then
        ok "hooks.json declares SessionStart + PostToolUse"
    else
        bad "hooks.json missing or does not declare both hooks"
    fi
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

# 5. Remote reachable + push-ready (no real push).
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

# 7. Orientation dry-run: what session start would inject. Cursor reaches the
# same hook through an adapter that takes the plugin root as argv[1], so the
# dry-run goes through whichever entry point the harness itself invokes.
if [ "$DIALECT" = "cursor" ]; then
    ENTRY="$PR/hooks/cursor-session-start.sh"
    ENTRY_REL="hooks/cursor-session-start.sh"
    ENTRY_CMD=(bash "$ENTRY" "$PR")
else
    ENTRY="$PR/hooks/session-start.sh"
    ENTRY_REL="hooks/session-start.sh"
    ENTRY_CMD=(bash "$ENTRY")
fi
if [ -f "$ENTRY" ]; then
    orient="$("${ENTRY_CMD[@]}" </dev/null 2>/dev/null || true)"
    if printf '%s' "$orient" | grep -q "durable memory"; then
        ok "orientation dry-run emits the session-start reminder"
        tail="$(printf '%s\n' "$orient" | awk '/last 5 log entries/{f=1} f' | grep '^## \[' | tail -1)"
        [ -n "$tail" ] && echo "        last log entry it would surface: $tail"
    else
        warn "session-start produced no orientation (is .llm-wiki attached and scaffolded?)"
    fi
else
    bad "$ENTRY_REL missing"
fi

# 8. Federation ask deps (optional; only /wiki-ask and /wiki-enroll need them).
miss=""
for c in jq curl; do command -v "$c" >/dev/null 2>&1 || miss="$miss $c"; done
command -v gh >/dev/null 2>&1 || miss="$miss gh(for /wiki-enroll)"
[ -z "$miss" ] && ok "federation ask deps present (jq, curl, gh)" || warn "ask deps missing:$miss — /wiki-ask and /wiki-enroll need them"

echo ""
echo "structural failures: $FAIL"
exit "$FAIL"
