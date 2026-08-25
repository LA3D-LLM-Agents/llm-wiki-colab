#!/usr/bin/env bash
#
# Claude Code PostToolUse hook (command type): after a Write or Edit to a
# wiki page, remind the agent to run the Verification Gate before
# committing. Installed by setup.sh --posttooluse-hook into
# .claude/hooks/posttooluse-hook.sh, then referenced from
# .claude/settings.json with matcher "Write|Edit".
#
# Why a command hook and not a prompt hook:
#   A command hook that exits 0 is purely advisory. The tool action
#   proceeds, and whatever the script writes to stdout is added to the
#   agent's context as a note. A prompt hook cannot do this: it is a
#   sandboxed single-turn model call with no filesystem or transcript
#   access, and its only outcomes are allow or block. An earlier version
#   of this hook used a prompt hook that asked the evaluator to check
#   index/log/back-reference state; the evaluator could not access those,
#   returned "not ok", and wrongly stopped the agent mid-ingest.
#
# This script does not evaluate the wiki itself (a shell hook has no way
# to). It only reminds the agent, which has tools, to run the gate. The
# canonical criteria live in core/agents/verification-gate.md.
#
# Reads the PostToolUse event JSON on stdin; always exits 0.

INPUT=$(cat)

# Extract the path of the file just written or edited. Two harness shapes:
#
#   Claude  tool_input.file_path is the target path.
#   Codex   tool_input carries only `command`, holding the apply_patch text;
#           there is no file_path field at all (probed on codex-cli 0.147.0).
#           The target paths are the `*** Add File:` / `*** Update File:` /
#           `*** Move to:` markers inside that patch.
#
# Claude behavior is unchanged: file_path is present there, so the patch-marker
# branch never runs. Empty on either path means no nudge, the same silent no-op
# the script already produced for every non-wiki edit.
FILE_PATH=""
PATCH_TARGETS=""
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
    if [ -z "$FILE_PATH" ]; then
        # Three separate -e expressions rather than one alternation: \| is a GNU
        # sed extension and this script also runs on macOS.
        PATCH_TARGETS=$(printf '%s' "$INPUT" \
            | jq -r '.tool_input.command // empty' 2>/dev/null \
            | sed -n \
                -e 's/^\*\*\* Add File: //p' \
                -e 's/^\*\*\* Update File: //p' \
                -e 's/^\*\*\* Move to: //p' \
            || true)
    fi
fi

# Nudge once if any target is a wiki page under the opt-in .llm-wiki/ dir.
# A patch may touch several files, so this scans all of them and stops at the
# first wiki page rather than emitting the advisory per file.
MATCHED=0
while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    case "$candidate" in
        */.llm-wiki/*.md|.llm-wiki/*.md) MATCHED=1; break ;;
    esac
done <<EOF
$FILE_PATH
$PATCH_TARGETS
EOF

if [ "$MATCHED" -eq 1 ]; then
    cat <<'EOF'
A wiki page was just written or edited. Before committing in the wiki
repo, run the Verification Gate (core/agents/verification-gate.md in the
llm-wiki plugin) over every page created or edited this session: every
numerical claim tagged with its corpus, every projection marked as such,
back-references bidirectional, and the index plus log updated. This is an
advisory reminder and does not block.
EOF
fi

exit 0
