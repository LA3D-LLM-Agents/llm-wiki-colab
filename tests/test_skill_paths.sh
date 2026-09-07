#!/usr/bin/env bash
# L1: every file a SKILL.md tells the model to run must exist in the subtree
# that ships it. A skill body is prose to every harness, so a stale script path
# surfaces only as a failed command mid-task.
#
# Scope note: this checks the TARGETS only. Which variable name a subtree should
# use (docs/deferred.md records that Codex and Cursor are meant to get
# $SKILL_DIRECTORY instead of ${CLAUDE_SKILL_DIR}) is an open product decision
# and is deliberately not asserted here.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT CODEX_PLUGIN_ROOT CURSOR_PLUGIN_ROOT

# A token runs to the first quote, backtick, or whitespace, which is how these
# paths are always delimited in the skill bodies.
# shellcheck disable=SC2016  # the ${...} here are literal tokens to match, not expansions
tokens() { grep -oh '\${CLAUDE_SKILL_DIR}[^"`'"'"' ]*\|\${CLAUDE_PLUGIN_ROOT}[^"`'"'"' ]*' "$1" 2>/dev/null | sort -u; }

found=0
for root in "$PLUGIN_ROOT" "$CODEX_PLUGIN_ROOT" "$CURSOR_PLUGIN_ROOT"; do
    subtree="$(basename "$(dirname "$(dirname "$root")")")"
    while IFS= read -r skill_md; do
        skill_dir="$(dirname "$skill_md")"
        while IFS= read -r token; do
            [ -n "$token" ] || continue
            found=$((found + 1))
            # Trailing punctuation from prose ("...run `x.sh`." ) is not part of
            # the path.
            path="${token%%[.,;:)]}"
            path="${path//\$\{CLAUDE_SKILL_DIR\}/$skill_dir}"
            path="${path//\$\{CLAUDE_PLUGIN_ROOT\}/$root}"
            assert_file "$path" "$subtree/$(basename "$skill_dir"): $token"
        done <<< "$(tokens "$skill_md")"
    done < <(find "$root/skills" -name SKILL.md -type f | sort)
done

# The extraction is a regex over prose: if it silently stops matching, every
# assertion above disappears and the file still exits 0.
if [ "$found" -ge 18 ]; then
    _pass "skill bodies name $found plugin-root/skill-dir paths across the three subtrees"
else
    _fail "skill path extraction found only $found tokens; expected at least 18"
fi

exit "$ASSERT_FAIL"
