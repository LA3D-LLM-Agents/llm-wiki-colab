#!/usr/bin/env bash
#
# Claude Code SessionStart hook (llm-wiki plugin): surface the project's wiki
# as durable memory at the start of a session.
#
# Opt-in contract: SILENT unless a gitignored .llm-wiki/ exists at the repo root.
# The plugin installs per machine, so this hook fires in every repo; only repos
# that ran /wiki-init (which creates .llm-wiki/) are oriented. A plain repo gets
# nothing, no nagging, and it never announces "no wiki".
#
# When .llm-wiki/ is present the hook emits a SINGLE JSON object on stdout:
#   - systemMessage (top-level): a one-line status banner the USER sees at
#     session start. Claude Code renders this directly, so it does not depend on
#     the model choosing to repeat injected context.
#   - hookSpecificOutput.additionalContext: orientation + the memory-boundary /
#     wiki-maintenance guidance + the wiki index + the last 5 log entries, all
#     injected into the model's context.
# When a hook emits JSON, stdout must be ONLY the JSON (plain text is ignored),
# so every model-facing block goes through additionalContext, not bare stdout.
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

PAGE_COUNT=$(find "$WIKI_DIR" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
LOG_FILE="$WIKI_DIR/log_${REPO_NAME}.md"
LOG_COUNT=$(grep -c '^## \[' "$LOG_FILE" 2>/dev/null || echo 0)

# The user-visible banner (top-level systemMessage).
BANNER="llm-wiki: durable memory active in ${REPO_NAME} (${PAGE_COUNT} pages, ${LOG_COUNT} log entries)"

# Build the model-facing context (goes into additionalContext).
CONTEXT="$(
    cat <<EOF
<system-reminder>
This project uses the wiki at .llm-wiki/ as durable memory. It is a separate
git repository with its own remote, NOT tracked by the main repo. Read
.llm-wiki/SCHEMA_${REPO_NAME}.md before non-trivial wiki edits. Update the wiki
proactively when experiment results, decisions, or syntheses emerge.

The wiki's current index (page catalog) and its last 5 log entries are included
in this session's context below. You already hold the wiki's current state:
treat the index as read, do not re-open index_${REPO_NAME}.md just to see what
pages exist or what changed recently. Open individual .llm-wiki/ page files only
when you need a page's actual contents.

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

    # Wiki index (catalog of pages).
    INDEX_FILE="$WIKI_DIR/index_${REPO_NAME}.md"
    if [[ -f "$INDEX_FILE" ]]; then
        echo
        echo "<system-reminder>"
        echo "## Wiki current state: index"
        echo
        cat "$INDEX_FILE"
        echo "</system-reminder>"
    fi

    # Last 5 log entries (append-only; newest at the bottom).
    if [[ -f "$LOG_FILE" ]]; then
        START_ENTRY=1
        if [[ "$LOG_COUNT" -gt 5 ]]; then
            START_ENTRY=$((LOG_COUNT - 4))
        fi
        echo
        echo "<system-reminder>"
        echo "## Wiki current state: last 5 log entries"
        echo
        awk -v s="$START_ENTRY" '/^## \[/{c++} c>=s' "$LOG_FILE"
        echo "</system-reminder>"
    fi
)"

# Emit the single JSON object. stdout must be ONLY this JSON. python3 is already
# a SessionStart dependency (ensure-wiki.py), so this adds no new requirement and
# handles all string escaping safely.
LW_BANNER="$BANNER" LW_CONTEXT="$CONTEXT" python3 -c '
import json, os
print(json.dumps({
    "systemMessage": os.environ["LW_BANNER"],
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": os.environ["LW_CONTEXT"],
    },
}))
'
