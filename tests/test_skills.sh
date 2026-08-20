#!/usr/bin/env bash
# L1: the plugin ships skills only, and each skill declares the invocation mode
# phase 1 chose for it. User-only skills carry disable-model-invocation; the
# three model-invocable skills must not, or the plugin's proactive behavior
# silently disappears.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

# name + description are the three-way lowest common denominator; every skill
# needs both regardless of harness.
for s in wiki-init wiki-doctor wiki-ask wiki-enroll wiki-lint wiki-source wiki-experiment; do
    f="$PLUGIN_ROOT/skills/$s/SKILL.md"
    assert_file "$f" "skill $s ships"
    assert_grep_file "$f" "name: $s" "skill $s declares its name"
    assert_grep_file "$f" "description:" "skill $s declares a description"
done

# The invocation mode lives in the frontmatter block; scoping the greps there
# keeps a body mention of the key from masking a missing (or smuggled) flag.
frontmatter() { sed -n '2,/^---$/p' "$1"; }

# User-only: invoked as /wiki-<name>, never chosen by the model.
for s in wiki-init wiki-doctor wiki-ask wiki-enroll; do
    if frontmatter "$PLUGIN_ROOT/skills/$s/SKILL.md" | grep -q 'disable-model-invocation: true'; then
        _pass "skill $s is user-invocable only"
    else
        _fail "skill $s is user-invocable only"
    fi
done

# Model-invocable: the plugin's proactive write/lint behavior depends on these
# staying model-selectable.
for s in wiki-lint wiki-source wiki-experiment; do
    if frontmatter "$PLUGIN_ROOT/skills/$s/SKILL.md" | grep -q 'disable-model-invocation'; then
        _fail "skill $s must stay model-invocable"
    else
        _pass "skill $s stays model-invocable"
    fi
done

# wiki-ask takes free-form user input; losing the placeholder makes it inert.
assert_grep_file "$PLUGIN_ROOT/skills/wiki-ask/SKILL.md" '$ARGUMENTS' \
    "wiki-ask still substitutes user input"

exit "$ASSERT_FAIL"
