#!/usr/bin/env bash
#
# Claude Code SessionStart hook (llm-wiki plugin): surface the project's wiki
# as durable memory at the start of a session.
#
# Opt-in contract: this hook is SILENT unless a gitignored .llm-wiki/ exists at
# the repo root. Because the plugin installs per machine, its hook fires in
# every repo; only repos that ran /wiki-init (which creates .llm-wiki/) get
# oriented. A plain repo gets nothing, no nagging.
#
# When .llm-wiki/ is present it emits, to stdout (captured as a system-reminder):
#   0. A one-line status announcement (the model is asked to surface it), so the
#      user sees at session start that the wiki is active + its page count.
#   1. Orientation + the memory-boundary / wiki-maintenance guidance.
#   2. The wiki index (catalog of pages), if present.
#   3. The last 5 log entries, for cross-session continuity.
# The absent case stays silent (opt-in), so it never announces "no wiki".
#
# The namespace is derived from origin at runtime (no install-time bake), so a
# single static plugin copy works in any repo. Internal wiki files stay
# namespaced (index_<repo>.md, log_<repo>.md, SCHEMA_<repo>.md).

set -uo pipefail

WIKI_DIR=".llm-wiki"

# Opt-in: no wiki here -> silent no-op.
[[ -d "$WIKI_DIR" ]] || exit 0

# Namespace from origin (mirrors ensure-wiki.py repo_name_from_origin and
# lib/git.sh lw_name_from_origin). Falls back to the checkout dir name.
name_from_origin() {
    local s="${1%.git}"
    s="${s%/}"
    case "$s" in
        *://*) s="${s#*://}"; s="${s#*/}" ;;   # scheme://host/owner/repo
        *@*:*) s="${s#*:}" ;;                    # scp user@host:owner/repo
    esac
    printf '%s' "${s##*/}"
}
ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
REPO_NAME="$(name_from_origin "$ORIGIN")"
[[ -n "$REPO_NAME" ]] || REPO_NAME="$(basename "$PWD")"

# Counts for the status announcement.
PAGE_COUNT=$(find "$WIKI_DIR" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
LOG_COUNT=$(grep -c '^## \[' "$WIKI_DIR/log_${REPO_NAME}.md" 2>/dev/null || echo 0)

# Block 0: status announcement. Surfaced to the user (the model is asked to say
# it out loud); the absent case stays silent above, so this only ever announces
# a wiki that exists.
cat <<EOF
<system-reminder>
llm-wiki: memory ACTIVE for this repo. A wiki is attached at .llm-wiki/
(namespace ${REPO_NAME}, ${PAGE_COUNT} pages, ${LOG_COUNT} log entries). Open
your first reply of this session with one short line telling the user the
llm-wiki is active and its page count, then address their request normally.
</system-reminder>
EOF

# Block 1: orientation.
cat <<EOF
<system-reminder>
This project uses the wiki at .llm-wiki/ as durable memory. It is a separate
git repository with its own remote, NOT tracked by the main repo. Read
.llm-wiki/SCHEMA_${REPO_NAME}.md before non-trivial wiki edits. Update the wiki
proactively when experiment results, decisions, or syntheses emerge.

Every wiki edit ends with a commit in the wiki's own repo:
  git -C .llm-wiki add <files>
  git -C .llm-wiki commit -m "..."
Run these without asking; local commits are reversible. Push only on explicit
request (use the wiki-write-protocol wrapper).

Slash commands: /wiki-init, /wiki-experiment, /wiki-source, /wiki-lint, /wiki-doctor.
</system-reminder>
EOF

# Fold in the memory-boundary / wiki-maintenance guidance shipped with the plugin.
GUIDANCE="${CLAUDE_PLUGIN_ROOT:-}/core/templates/guidance.md"
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" && -f "$GUIDANCE" ]]; then
    echo
    echo "<system-reminder>"
    cat "$GUIDANCE"
    echo "</system-reminder>"
fi

# Block 2: wiki index.
INDEX_FILE="$WIKI_DIR/index_${REPO_NAME}.md"
if [[ -f "$INDEX_FILE" ]]; then
    echo
    echo "<system-reminder>"
    echo "## Wiki current state — index"
    echo
    cat "$INDEX_FILE"
    echo "</system-reminder>"
fi

# Block 3: last 5 log entries (append-only, newest at the bottom).
LOG_FILE="$WIKI_DIR/log_${REPO_NAME}.md"
if [[ -f "$LOG_FILE" ]]; then
    TOTAL_ENTRIES=$(grep -c '^## \[' "$LOG_FILE" 2>/dev/null || echo 0)
    START_ENTRY=1
    if [[ "$TOTAL_ENTRIES" -gt 5 ]]; then
        START_ENTRY=$((TOTAL_ENTRIES - 4))
    fi
    echo
    echo "<system-reminder>"
    echo "## Wiki current state — last 5 log entries"
    echo
    awk -v s="$START_ENTRY" '/^## \[/{c++} c>=s' "$LOG_FILE"
    echo "</system-reminder>"
fi
