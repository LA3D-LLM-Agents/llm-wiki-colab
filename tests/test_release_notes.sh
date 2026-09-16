#!/usr/bin/env bash
# Release-note scope filtering, using git-cliff against a disposable history.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"
command -v git-cliff >/dev/null 2>&1 || { echo "  FAIL git-cliff is required"; exit 1; }
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR GIT_CEILING_DIRECTORIES
SCRATCH="$(mk_scratch)"
trap 'rm -rf "$SCRATCH"' EXIT INT TERM
git -C "$SCRATCH" commit --allow-empty -qm "chore: seed"
git -C "$SCRATCH" tag v1.0.0
for scope in ci dev docs build deps act test tests publish release harness scripts; do
    git -C "$SCRATCH" commit --allow-empty -qm "feat($scope): internal-$scope-probe"
done
git -C "$SCRATCH" commit --allow-empty -qm "fix(wiki-init): preserve project identity"
git -C "$SCRATCH" commit --allow-empty -qm "feat(hooks)!: remove obsolete hook" \
    -m "BREAKING CHANGE: the obsolete hook is removed."
git -C "$SCRATCH" commit --allow-empty -qm "feat(build)!: change the shipped manifest" \
    -m "BREAKING CHANGE: the manifest description changes."
render() {
    local status=0
    git-cliff -v --repository "$SCRATCH" --config "$ROOT/cliff.toml" \
        --unreleased --strip all 2> "$SCRATCH/render.stderr" || status=$?
    if [ "$status" -ne 0 ]; then cat "$SCRATCH/render.stderr" >&2; fi
    return "$status"
}
NOTES="$(render)" || { _fail "git-cliff failed to render"; exit "$ASSERT_FAIL"; }
for scope in ci dev docs build deps act test tests publish release harness scripts; do
    assert_not_contains "$NOTES" "Internal-$scope-probe" "notes exclude internal $scope features"
done
assert_contains "$NOTES" 'Preserve project identity' "notes retain shipped fixes"
assert_contains "$NOTES" '**Breaking:** `hooks`: Remove obsolete hook' "notes mark shipped breaking changes"
assert_contains "$NOTES" '**Breaking:** `build`: Change the shipped manifest' "breaking protection overrides internal scopes"

# Adding another legitimate entry must preserve the existing decisions.
git -C "$SCRATCH" commit --allow-empty -qm "feat(wiki-init): support another wiki"
NOTES="$(render)" || { _fail "git-cliff failed to render"; exit "$ASSERT_FAIL"; }
assert_contains "$NOTES" 'Support another wiki' "notes accept an additional shipped feature"
assert_contains "$NOTES" 'Preserve project identity' "adding a feature preserves the shipped fix"
assert_not_contains "$NOTES" 'Internal-release-probe' "adding a feature preserves internal filtering"
exit "$ASSERT_FAIL"
