#!/usr/bin/env bash
#
# Cursor sessionStart hook (llm-wiki plugin): surface the project's wiki
# as durable memory at the start of a session.
#
# Opt-in contract: SILENT (empty additional_context) unless a gitignored
# .llm-wiki/ exists at the repo root. The plugin installs per machine, so this
# hook fires in every repo; only repos that ran /wiki-init are oriented.
#
# When .llm-wiki/ is present the hook emits a SINGLE JSON object on stdout:
#   {"additional_context": "<banner + orientation + guidance + index + last-5>"}
# Cursor has no systemMessage channel; the one-line banner is the first line of
# additional_context.
#
# Namespace is derived from origin at runtime (no install-time bake).

set -uo pipefail

# Drain stdin (Cursor sends sessionStart input JSON).
cat >/dev/null

emit_empty() {
    printf '%s\n' '{"additional_context":""}'
    exit 0
}

WIKI_DIR=".llm-wiki"

# Opt-in: no wiki here -> empty context (Cursor expects valid JSON).
[[ -d "$WIKI_DIR" ]] || emit_empty

name_from_origin() {
    local s="${1%.git}"
    s="${s%/}"
    case "$s" in
        *://*) s="${s#*://}"; s="${s#*/}" ;;
        *@*:*) s="${s#*:}" ;;
    esac
    printf '%s' "${s##*/}"
}
ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
REPO_NAME="$(name_from_origin "$ORIGIN")"
[[ -n "$REPO_NAME" ]] || REPO_NAME="$(basename "$PWD")"

PAGE_COUNT=$(find "$WIKI_DIR" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
LOG_FILE="$WIKI_DIR/log_${REPO_NAME}.md"
LOG_COUNT=$(grep -c '^## \[' "$LOG_FILE" 2>/dev/null || echo 0)

BANNER="llm-wiki: durable memory active in ${REPO_NAME} (${PAGE_COUNT} pages, ${LOG_COUNT} log entries)"

CONTEXT="$(
    echo "$BANNER"
    echo
    cat <<EOF
## Wiki as project memory (session start)

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

Commands: /wiki-init, /wiki-experiment, /wiki-source, /wiki-lint, /wiki-doctor.
EOF

    GUIDANCE="${CURSOR_PLUGIN_ROOT:-}/core/templates/guidance.md"
    if [[ -n "${CURSOR_PLUGIN_ROOT:-}" && -f "$GUIDANCE" ]]; then
        echo
        cat "$GUIDANCE"
    fi

    INDEX_FILE="$WIKI_DIR/index_${REPO_NAME}.md"
    if [[ -f "$INDEX_FILE" ]]; then
        echo
        echo "## Wiki current state: index"
        echo
        cat "$INDEX_FILE"
    fi

    if [[ -f "$LOG_FILE" ]]; then
        START_ENTRY=1
        if [[ "$LOG_COUNT" -gt 5 ]]; then
            START_ENTRY=$((LOG_COUNT - 4))
        fi
        echo
        echo "## Wiki current state: last 5 log entries"
        echo
        awk -v s="$START_ENTRY" '/^## \[/{c++} c>=s' "$LOG_FILE"
    fi
)"

# Emit Cursor JSON. Prefer python3; fall back to jq; else empty.
if command -v python3 >/dev/null 2>&1; then
    LW_CONTEXT="$CONTEXT" python3 -c 'import json,os; print(json.dumps({"additional_context": os.environ["LW_CONTEXT"]}))'
elif command -v jq >/dev/null 2>&1; then
    printf '%s' "$CONTEXT" | jq -Rs '{additional_context: .}'
else
    emit_empty
fi
