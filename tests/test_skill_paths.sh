#!/usr/bin/env bash
# L1: every file a SKILL.md tells the model to run must exist in the subtree
# that ships it, and the variable that names the skill directory must be the
# one that harness resolves. A skill body is prose to every harness, so a stale
# script path or a foreign variable surfaces only as a failed command mid-task.
#
# Claude Code sets CLAUDE_SKILL_DIR in the shell that runs a skill's commands.
# Codex and Cursor set nothing; they show the model the SKILL.md path and the
# model substitutes it into the $SKILL_DIRECTORY placeholder, which fails
# loudly on an empty expansion rather than running a silent wrong path.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT CODEX_PLUGIN_ROOT CURSOR_PLUGIN_ROOT

# A token runs to the first quote, backtick, or whitespace, which is how these
# paths are always delimited in the skill bodies.
# shellcheck disable=SC2016  # the ${...} here are literal tokens to match, not expansions
tokens() { grep -oh '\${CLAUDE_SKILL_DIR}[^"`'"'"' ]*\|\$SKILL_DIRECTORY[^"`'"'"' ]*\|\${CLAUDE_PLUGIN_ROOT}[^"`'"'"' ]*' "$1" 2>/dev/null | sort -u; }

# subtree root -> the skill-directory variable that subtree must use, and the
# one it must not.
# shellcheck disable=SC2016  # literal variable spellings, not expansions
skill_var() {
    case "$1" in
        "$PLUGIN_ROOT") printf '%s' '${CLAUDE_SKILL_DIR}' ;;
        *) printf '%s' '$SKILL_DIRECTORY' ;;
    esac
}
foreign_var() {
    case "$1" in
        "$PLUGIN_ROOT") printf '%s' 'SKILL_DIRECTORY' ;;
        *) printf '%s' 'CLAUDE_SKILL_DIR' ;;
    esac
}

found=0
for root in "$PLUGIN_ROOT" "$CODEX_PLUGIN_ROOT" "$CURSOR_PLUGIN_ROOT"; do
    subtree="$(basename "$(dirname "$(dirname "$root")")")"
    while IFS= read -r skill_md; do
        skill_dir="$(dirname "$skill_md")"
        label="$subtree/$(basename "$skill_dir")"
        if grep -q "$(foreign_var "$root")" "$skill_md"; then
            _fail "$label names $(foreign_var "$root"), which $subtree does not resolve"
        else
            _pass "$label uses only the $subtree skill-directory variable"
        fi
        while IFS= read -r token; do
            [ -n "$token" ] || continue
            found=$((found + 1))
            # Trailing punctuation from prose ("...run `x.sh`." ) is not part of
            # the path.
            path="${token%%[.,;:)]}"
            var="$(skill_var "$root")"
            path="${path//"$var"/$skill_dir}"
            path="${path//\$\{CLAUDE_PLUGIN_ROOT\}/$root}"
            assert_file "$path" "$label: $token"
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

# The source tree must write the Claude spelling and let the build do the one
# rewrite; a placeholder hand-written into the source would ship into the
# Claude subtree where nothing sets it. Exercised on a scratch copy, since
# assemble.py locates its inputs relative to itself.
scratch="$(mktemp -d)"
cp -R "$ROOT/build" "$ROOT/plugins" "$ROOT/VERSION" "$ROOT/CITATION.cff" "$ROOT/LICENSE" "$scratch/"
rm -rf "$scratch/build/out"
# shellcheck disable=SC2016  # literal placeholder written into the fixture
printf '\nRun `bash "$SKILL_DIRECTORY/scripts/init-wiki.sh"`.\n' >> "$scratch/plugins/llm-wiki/skills/wiki-init/SKILL.md"
if err="$(uv run "$scratch/build/assemble.py" --out "$scratch/out" \
        --owner-repo o/r --source-ref 0000000000000000000000000000000000000000 2>&1 >/dev/null)"; then
    _fail "build accepted a source skill body carrying the placeholder"
else
    assert_contains "$err" "CLAUDE_SKILL_DIR" "build refuses a source skill body carrying the placeholder"
fi
rm -rf "$scratch"

exit "$ASSERT_FAIL"
