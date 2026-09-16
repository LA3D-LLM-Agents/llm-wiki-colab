#!/usr/bin/env bash
# L1: a publish to main tags the source commit with the version it shipped,
# and build/publish.py --verify rebuilds a published tree from the source
# commit its message records, refusing unless the hashes match.
#
# Like test_publish_gate.sh this reads the source tree, because publish.py is
# source tooling with no artifact copy. Everything happens in a throwaway git
# repo, so this repo's refs and tags are never touched.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

command -v git >/dev/null 2>&1 || { echo "  FAIL git is required"; exit 1; }
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR GIT_CEILING_DIRECTORIES

VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"

SCRATCH="$(mk_scratch https://github.com/LA3D-LLM-Agents/llm-wiki-colab.git)"
trap 'rm -rf "$SCRATCH"' EXIT INT TERM

# tests/ is deliberately NOT copied: every publish passes --skip-gates, and a
# forgotten flag then fails loudly instead of recursing into this file.
cp -r "$ROOT/build" "$ROOT/plugins" "$SCRATCH/"
cp "$ROOT/CITATION.cff" "$ROOT/LICENSE" "$ROOT/VERSION" "$SCRATCH/"

# Source history lives on src, with VERSION committed so a source commit is
# enough to rebuild from. main starts as an unrelated empty root commit, the
# bootstrap shape publish.py waives the version gate for.
git -C "$SCRATCH" symbolic-ref HEAD refs/heads/src
git -C "$SCRATCH" add -A
git -C "$SCRATCH" commit -qm "seed: source tree"
SEED="$(git -C "$SCRATCH" rev-parse HEAD)"
BOOT="$(git -C "$SCRATCH" commit-tree "$(git -C "$SCRATCH" mktree </dev/null)" -m "bootstrap: empty main")"
git -C "$SCRATCH" update-ref refs/heads/main "$BOOT"

OUTPUT=""
STATUS=0
pub() {
    OUTPUT="$(cd "$SCRATCH" && uv run "$SCRATCH/build/publish.py" "$@" 2>&1)"
    STATUS=$?
}
tip() { git -C "$SCRATCH" rev-parse --verify --quiet "$1" || echo "(none)"; }

# --- 1. a throwaway branch mints no tag --------------------------------------
pub --branch pub --skip-gates
[ "$STATUS" -eq 0 ] && _pass "publish to a throwaway branch succeeds" \
    || _fail "publish to pub failed (exit $STATUS): $OUTPUT"
[ "$(tip "refs/tags/v$VERSION")" = "(none)" ] \
    && _pass "a throwaway branch mints no release tag" \
    || _fail "publishing to pub minted v$VERSION"
assert_contains "$(git -C "$SCRATCH" log -1 --format=%b pub)" "gates: skipped" \
    "the publish commit records that the suite was skipped"

# --- 2. a publish to main tags the source commit -----------------------------
pub --branch main --skip-gates --allow-main
[ "$STATUS" -eq 0 ] && _pass "publish to main succeeds" \
    || _fail "publish to main failed (exit $STATUS): $OUTPUT"
[ "$(tip "refs/tags/v$VERSION")" = "$SEED" ] \
    && _pass "v$VERSION names the source commit main was published from" \
    || _fail "v$VERSION names $(tip "refs/tags/v$VERSION"), not the source $SEED"
assert_contains "$OUTPUT" "tag:        v$VERSION" "the publish report names the tag"

# --- 3. --verify rebuilds main from the source commit -------------------------
pub --verify main --allow-skipped-gates
[ "$STATUS" -eq 0 ] && _pass "--verify accepts a tree that rebuilds from its source" \
    || _fail "--verify refused a reproducible tree (exit $STATUS): $OUTPUT"
assert_contains "$OUTPUT" "reproduces from its source commit" "--verify says the trees match"

pub --verify main
[ "$STATUS" -eq 1 ] && _pass "--verify refuses a publish whose suite was skipped" \
    || _fail "--verify accepted a skipped-gates publish (exit $STATUS)"
assert_contains "$OUTPUT" "skip-gates" "the refusal names the skipped suite"
assert_not_contains "$OUTPUT" "===== assemble" "a skipped-gates refusal costs no rebuild"

# --- 4. --tag cross-checks the tag against the source and the version --------
pub --verify main --allow-skipped-gates --tag "v$VERSION"
[ "$STATUS" -eq 0 ] && _pass "--tag accepts the tag main was published under" \
    || _fail "--tag refused v$VERSION (exit $STATUS): $OUTPUT"

pub --verify main --allow-skipped-gates --tag v99.9.9
[ "$STATUS" -eq 1 ] && _pass "--tag refuses a tag that does not exist" \
    || _fail "--tag accepted a missing tag (exit $STATUS)"
assert_contains "$OUTPUT" "does not exist" "the refusal says the tag is missing"

git -C "$SCRATCH" update-ref refs/tags/v0.0.1 "$BOOT"
pub --verify main --allow-skipped-gates --tag v0.0.1
[ "$STATUS" -eq 1 ] && _pass "--tag refuses a tag on a commit other than the source" \
    || _fail "--tag accepted a tag on the wrong commit (exit $STATUS)"
assert_contains "$OUTPUT" "was published from" "the refusal names the recorded source"

git -C "$SCRATCH" update-ref refs/tags/v98.0.0 "$SEED"
pub --verify main --allow-skipped-gates --tag v98.0.0
[ "$STATUS" -eq 1 ] && _pass "--tag refuses a tag whose version is not the tree's" \
    || _fail "--tag accepted a version mismatch (exit $STATUS)"
assert_contains "$OUTPUT" "carries VERSION $VERSION" "the refusal names the tree's version"

# --- 5. --reachable-from: the source must still be in the source history -----
pub --verify main --allow-skipped-gates --reachable-from src
[ "$STATUS" -eq 0 ] && _pass "--reachable-from accepts a source on the source branch" \
    || _fail "--reachable-from refused an ancestor (exit $STATUS): $OUTPUT"
pub --verify main --allow-skipped-gates --reachable-from main
[ "$STATUS" -eq 1 ] && _pass "--reachable-from refuses a source outside the ref's history" \
    || _fail "--reachable-from accepted a non-ancestor (exit $STATUS)"
assert_contains "$OUTPUT" "not an ancestor" "the refusal says the source is unreachable"

# --- 6. a publish made from uncommitted edits does not reproduce -------------
printf '\nA sentence that was never committed.\n' \
    >> "$SCRATCH/plugins/llm-wiki/skills/wiki-lint/SKILL.md"
echo "99.0.0" > "$SCRATCH/VERSION"
pub --branch main --skip-gates --allow-main
[ "$STATUS" -eq 0 ] && _pass "a dirty working copy still publishes (the gate is --verify)" \
    || _fail "publish from a dirty working copy failed (exit $STATUS): $OUTPUT"
pub --verify main --allow-skipped-gates
[ "$STATUS" -eq 1 ] && _pass "--verify refuses a tree published from uncommitted edits" \
    || _fail "--verify accepted an irreproducible tree (exit $STATUS)"
assert_contains "$OUTPUT" "differs from published tree" "the refusal names the mismatch"
assert_contains "$OUTPUT" "VERSION" "the refusal lists the uncommitted VERSION"
assert_contains "$OUTPUT" "wiki-lint/SKILL.md" "the refusal lists the uncommitted skill edit"

# --- 7. a stale tag on another commit is refused before the suite -------------
git -C "$SCRATCH" add -A
git -C "$SCRATCH" commit -qm "feat: the edits, committed this time"
HEAD2="$(git -C "$SCRATCH" rev-parse HEAD)"
printf '\nOne more sentence.\n' >> "$SCRATCH/plugins/llm-wiki/skills/wiki-lint/SKILL.md"
echo "99.0.1" > "$SCRATCH/VERSION"
git -C "$SCRATCH" add -A
git -C "$SCRATCH" commit -qm "chore: bump to 99.0.1"
HEAD3="$(git -C "$SCRATCH" rev-parse HEAD)"
git -C "$SCRATCH" update-ref refs/tags/v99.0.1 "$BOOT"
BEFORE="$(tip refs/heads/main)"
pub --branch main --allow-main
[ "$STATUS" -eq 1 ] && _pass "a release tag already on another commit is refused" \
    || _fail "publish clobbered or ignored a stale v99.0.1 (exit $STATUS)"
assert_contains "$OUTPUT" "already names" "the refusal names the stale tag"
assert_not_contains "$OUTPUT" "===== gates" "the stale tag is refused before the suite runs"
[ "$(tip refs/heads/main)" = "$BEFORE" ] && _pass "a refused publish leaves main alone" \
    || _fail "main moved on a refused publish"
[ "$(tip refs/tags/v99.0.1)" = "$BOOT" ] && _pass "a refused publish leaves the stale tag alone" \
    || _fail "the stale tag was moved"

git -C "$SCRATCH" update-ref -d refs/tags/v99.0.1
pub --branch main --skip-gates --allow-main
[ "$STATUS" -eq 0 ] && _pass "the same publish succeeds once the stale tag is gone" \
    || _fail "publish failed after removing the stale tag (exit $STATUS): $OUTPUT"
[ "$(tip refs/tags/v99.0.1)" = "$HEAD3" ] && _pass "v99.0.1 names the new source commit" \
    || _fail "v99.0.1 names $(tip refs/tags/v99.0.1), not $HEAD3"
[ "$HEAD2" != "$HEAD3" ] && _pass "the fixture really advanced the source history" \
    || _fail "fixture error: HEAD did not advance"
pub --verify main --allow-skipped-gates --tag v99.0.1 --reachable-from src
[ "$STATUS" -eq 0 ] && _pass "a clean publish verifies with its tag and source branch" \
    || _fail "--verify refused a clean publish (exit $STATUS): $OUTPUT"

exit "$ASSERT_FAIL"
