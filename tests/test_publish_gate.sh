#!/usr/bin/env bash
# L1: build/publish.py refuses to publish a changed tree that reuses the
# version the target branch already carries, and stamps one VERSION into every
# manifest it emits.
#
# This is the only test that reads the source tree rather than build output.
# It has to: publish.py is source tooling, it needs a real .git, and there is no
# artifact copy of it. Everything happens inside a throwaway git repo built by
# copying the source tree, so this repo's refs are never touched.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"

command -v git >/dev/null 2>&1 || { echo "  FAIL git is required"; exit 1; }

# Ambient git redirection (GIT_DIR and friends, exported by git hooks, bisect
# run, and some CI wrappers) would aim the plumbing below and publish.py's own
# git calls at a repository this test was never pointed at; scrub it so the
# scratch repo is the only one in play.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR GIT_CEILING_DIRECTORIES

VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"

# The scratch repo gets an origin so assemble.py's default_owner_repo resolves;
# publish.py passes only --source-ref through to it.
SCRATCH="$(mk_scratch https://github.com/LA3D-LLM-Agents/llm-wiki-colab.git)"
trap 'rm -rf "$SCRATCH"' EXIT INT TERM

# tests/ is deliberately NOT copied. Every publish below passes --skip-gates,
# and leaving the runner out means a forgotten flag fails loudly instead of
# recursing into this file.
cp -r "$ROOT/build" "$ROOT/plugins" "$SCRATCH/"
cp "$ROOT/CITATION.cff" "$ROOT/LICENSE" "$SCRATCH/"

# git init leaves HEAD on whatever init.defaultBranch says; publish.py falls
# back to refs/heads/main for a branch's first parent, so name it explicitly.
git -C "$SCRATCH" symbolic-ref HEAD refs/heads/main
git -C "$SCRATCH" add -A
git -C "$SCRATCH" commit -qm "seed: source tree with no VERSION"

# VERSION lands after the seed commit on purpose: the seed's tree carries
# neither a VERSION file nor an emitted manifest, which is the bootstrap case.
cp "$ROOT/VERSION" "$SCRATCH/VERSION"

OUTPUT=""
STATUS=0
pub() {
    OUTPUT="$(cd "$SCRATCH" && uv run "$SCRATCH/build/publish.py" "$@" 2>&1)"
    STATUS=$?
}
tip() { git -C "$SCRATCH" rev-parse --verify --quiet "refs/heads/$1" || echo "(none)"; }
blob() { git -C "$SCRATCH" show "$1:$2" 2>/dev/null; }

# --- 1. bootstrap: a parent that records no version must not crash ------------
pub --branch pub --skip-gates
[ "$STATUS" -eq 0 ] && _pass "bootstrap publish succeeds against a version-less parent" \
    || _fail "bootstrap publish failed (exit $STATUS): $OUTPUT"
assert_contains "$OUTPUT" "bootstrap" "bootstrap publish says the gate was not applied"

# --- 2. one VERSION read reaches every manifest in the published tree ---------
[ "$(blob pub VERSION | tr -d '[:space:]')" = "$VERSION" ] \
    && _pass "published tree carries VERSION $VERSION at its root" \
    || _fail "published VERSION is not $VERSION"
[ "$(blob pub claude/plugins/llm-wiki/.claude-plugin/plugin.json | jq -r .version)" = "$VERSION" ] \
    && _pass "published claude manifest carries $VERSION" \
    || _fail "published claude manifest version is not $VERSION"
[ "$(blob pub codex/plugins/llm-wiki/.codex-plugin/plugin.json | jq -r .version)" = "$VERSION" ] \
    && _pass "published codex manifest carries $VERSION" \
    || _fail "published codex manifest version is not $VERSION"
assert_contains "$(blob pub CITATION.cff)" "version: \"$VERSION\"" \
    "published CITATION.cff carries $VERSION"
assert_contains "$(git -C "$SCRATCH" log -1 --format=%s pub)" "publish $VERSION" \
    "publish commit subject names the version"
assert_contains "$(git -C "$SCRATCH" log -1 --format=%b pub)" "version: $VERSION" \
    "publish commit body carries a version trailer"

# --- 3. unchanged tree, unchanged version: the pre-existing path -------------
BEFORE="$(tip pub)"
pub --branch pub --skip-gates
assert_contains "$OUTPUT" "nothing to publish" "an unchanged tree still publishes nothing"
[ "$(tip pub)" = "$BEFORE" ] && _pass "an unchanged tree leaves the branch tip alone" \
    || _fail "the branch tip moved on an unchanged tree"

# --- 4. THE GATE: changed tree, no bump --------------------------------------
printf '\nA sentence added to make the tree differ.\n' \
    >> "$SCRATCH/plugins/llm-wiki/skills/wiki-lint/SKILL.md"
BEFORE="$(tip pub)"
pub --branch pub --skip-gates
[ "$STATUS" -eq 1 ] && _pass "a changed tree with no version bump is refused" \
    || _fail "a changed tree with no version bump published (exit $STATUS)"
assert_contains "$OUTPUT" "version gate" "the refusal names the version gate"
assert_contains "$OUTPUT" "Bump VERSION" "the refusal says what to do"
[ "$(tip pub)" = "$BEFORE" ] && _pass "a refused publish leaves the branch tip alone" \
    || _fail "the branch tip moved on a refused publish"

# Every case above set --skip-gates, so the refusal already proves the version
# gate survives it. Run the same case without the flag to prove the other half:
# the gate refuses before the behavior suite is reached. This scratch repo has
# no tests/ directory, so any run that got as far as the suite says so loudly.
pub --branch pub
assert_contains "$OUTPUT" "version gate" "the version gate runs without --skip-gates too"
assert_not_contains "$OUTPUT" "===== gates" \
    "the version gate refuses before the behavior suite runs"

# --- 5. the override, on a throwaway branch ----------------------------------
pub --branch pub --skip-gates --force-version
[ "$STATUS" -eq 0 ] && _pass "--force-version publishes a changed tree with no bump" \
    || _fail "--force-version did not publish (exit $STATUS): $OUTPUT"
assert_contains "$OUTPUT" "--force-version set" "--force-version warns that the gate did not run"

# --- 6. the green half: a bump publishes -------------------------------------
printf '\nAnother sentence.\n' >> "$SCRATCH/plugins/llm-wiki/skills/wiki-lint/SKILL.md"
echo "99.0.0" > "$SCRATCH/VERSION"
pub --branch pub --skip-gates
[ "$STATUS" -eq 0 ] && _pass "a changed tree with a bumped VERSION publishes" \
    || _fail "a bumped VERSION did not publish (exit $STATUS): $OUTPUT"
[ "$(blob pub VERSION | tr -d '[:space:]')" = "99.0.0" ] \
    && _pass "the published tree carries the bumped version" \
    || _fail "the published tree does not carry the bumped version"

# --- 7. published history must not go backwards ------------------------------
printf '\nA third sentence.\n' >> "$SCRATCH/plugins/llm-wiki/skills/wiki-lint/SKILL.md"
echo "98.0.0" > "$SCRATCH/VERSION"
BEFORE="$(tip pub)"
pub --branch pub --skip-gates
[ "$STATUS" -eq 1 ] && _pass "a decreased VERSION is refused" \
    || _fail "a decreased VERSION published (exit $STATUS)"
assert_contains "$OUTPUT" "lower than" "the refusal says the version went backwards"
[ "$(tip pub)" = "$BEFORE" ] && _pass "a decreased VERSION leaves the branch tip alone" \
    || _fail "the branch tip moved on a decreased VERSION"

# --- 8. the override is unavailable where it matters -------------------------
echo "99.0.1" > "$SCRATCH/VERSION"
BEFORE="$(tip main)"
pub --branch main --skip-gates --allow-main --force-version
[ "$STATUS" -eq 1 ] && _pass "--force-version is refused for main" \
    || _fail "--force-version was accepted for main (exit $STATUS)"
assert_contains "$OUTPUT" "refused for main" "the main refusal says why"
assert_not_contains "$OUTPUT" "===== assemble" "the main refusal costs no assemble"
[ "$(tip main)" = "$BEFORE" ] && _pass "refusing --force-version leaves main alone" \
    || _fail "main moved despite the refusal"

# --- 9. a parent published before the VERSION file existed -------------------
# Rebuild the current artifact tree minus its VERSION file: that is exactly the
# shape of every commit already on main, and the gate must read the version out
# of the emitted Claude manifest rather than waive itself.
LEGACY_TREE="$(
    GIT_INDEX_FILE="$SCRATCH/.legacy-index" git -C "$SCRATCH" read-tree pub \
    && GIT_INDEX_FILE="$SCRATCH/.legacy-index" git -C "$SCRATCH" update-index --force-remove VERSION \
    && GIT_INDEX_FILE="$SCRATCH/.legacy-index" git -C "$SCRATCH" write-tree
)"
rm -f "$SCRATCH/.legacy-index"
LEGACY_COMMIT="$(git -C "$SCRATCH" commit-tree "$LEGACY_TREE" -p "$(tip pub)" -m "artifact predating VERSION")"
git -C "$SCRATCH" update-ref refs/heads/legacy "$LEGACY_COMMIT"
LEGACY_VERSION="$(blob legacy claude/plugins/llm-wiki/.claude-plugin/plugin.json | jq -r .version)"
[ -z "$(blob legacy VERSION)" ] && _pass "the legacy parent really carries no VERSION file" \
    || _fail "the legacy fixture still has a VERSION file"

echo "$LEGACY_VERSION" > "$SCRATCH/VERSION"
printf '\nA fourth sentence.\n' >> "$SCRATCH/plugins/llm-wiki/skills/wiki-lint/SKILL.md"
pub --branch legacy --skip-gates
[ "$STATUS" -eq 1 ] && _pass "a version-less parent still gates via its claude manifest" \
    || _fail "a version-less parent waived the gate (exit $STATUS): $OUTPUT"
assert_contains "$OUTPUT" ".claude-plugin/plugin.json" \
    "the refusal names the manifest it read the previous version from"

# --- 10. a parent shaped like today's real main ------------------------------
# Real main still carries the pre-restructure layout: no VERSION file, no
# claude/ subtree, only adapters/claude-code/.claude-plugin/plugin.json. The
# first gated publish onto it must read that manifest, not take the waiver.
PREMAIN_SRC="$SCRATCH/.premain-tree"
mkdir -p "$PREMAIN_SRC/adapters/claude-code/.claude-plugin"
printf '{"name": "llm-wiki", "version": "0.1.3"}\n' \
    > "$PREMAIN_SRC/adapters/claude-code/.claude-plugin/plugin.json"
PREMAIN_TREE="$(
    GIT_INDEX_FILE="$SCRATCH/.premain-index" \
        git --git-dir="$SCRATCH/.git" --work-tree="$PREMAIN_SRC" -C "$PREMAIN_SRC" add -A . \
    && GIT_INDEX_FILE="$SCRATCH/.premain-index" git -C "$SCRATCH" write-tree
)"
rm -f "$SCRATCH/.premain-index"
PREMAIN_COMMIT="$(git -C "$SCRATCH" commit-tree "$PREMAIN_TREE" -m "pre-restructure main layout")"
git -C "$SCRATCH" update-ref refs/heads/premain "$PREMAIN_COMMIT"
git -C "$SCRATCH" update-ref refs/heads/premain-down "$PREMAIN_COMMIT"
[ -z "$(blob premain VERSION)" ] && [ -z "$(blob premain claude/plugins/llm-wiki/.claude-plugin/plugin.json)" ] \
    && _pass "the premain parent carries neither VERSION nor the claude manifest" \
    || _fail "the premain fixture does not match real main's layout"

cp "$ROOT/VERSION" "$SCRATCH/VERSION"
pub --branch premain --skip-gates
[ "$STATUS" -eq 0 ] && _pass "a bump over the pre-restructure layout publishes" \
    || _fail "publish over the pre-restructure parent failed (exit $STATUS): $OUTPUT"
assert_not_contains "$OUTPUT" "bootstrap" \
    "the pre-restructure parent is gated, not waived"

echo "0.1.0" > "$SCRATCH/VERSION"
BEFORE="$(tip premain-down)"
pub --branch premain-down --skip-gates
[ "$STATUS" -eq 1 ] && _pass "a downgrade below the adapters manifest is refused" \
    || _fail "a downgrade below the adapters manifest published (exit $STATUS)"
assert_contains "$OUTPUT" "adapters/claude-code/.claude-plugin/plugin.json" \
    "the refusal names the adapters manifest it read"
[ "$(tip premain-down)" = "$BEFORE" ] && _pass "the premain branch tip is unmoved on refusal" \
    || _fail "the premain branch tip moved on a refused downgrade"
cp "$ROOT/VERSION" "$SCRATCH/VERSION"

exit "$ASSERT_FAIL"
