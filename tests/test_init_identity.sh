#!/usr/bin/env bash
# L3: /wiki-init attributes the initialization commits to the identity the host
# project commits with. The wiki is a separate checkout nested inside the host,
# so Git alone never sees the host's local user.name and user.email; the
# initializer must carry them over. Precedence: an identity the wiki already
# has, then the host project's local one, then the global one. With none of
# those, initialization stops with a named status instead of guessing.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

INIT="$PLUGIN_ROOT/skills/wiki-init/scripts/init-wiki.sh"

# Only the configuration this test writes can supply an identity.
export GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL="$(mktemp)"; export GIT_CONFIG_GLOBAL
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL EMAIL

set_global() { printf '[user]\n\tname = %s\n\temail = %s\n' "$1" "$2" > "$GIT_CONFIG_GLOBAL"; }
clear_global() { : > "$GIT_CONFIG_GLOBAL"; }

# host [name email] -> fresh host repo, with a local identity when given.
host() {
    local d
    d="$(mktemp -d)"; d="$(cd "$d" && pwd -P)"
    git -C "$d" init -q
    git -C "$d" remote add origin https://github.com/foo/bar.git
    if [ $# -eq 2 ]; then git -C "$d" config user.name "$1"; git -C "$d" config user.email "$2"; fi
    echo "$d"
}
init() { ( cd "$1" && bash "$INIT" --agent claude-code 2>/dev/null ); }
# idents DIR -> the distinct author/committer identities across every wiki commit.
idents() { git -C "$1/.llm-wiki" log --format='%an <%ae> %cn <%ce>' 2>/dev/null | sort -u; }
assert_idents() {
    local got; got="$(idents "$1")"
    if [ "$got" = "$2 $2" ]; then _pass "$3"; else _fail "$3 (got: ${got:-no commits})"; fi
}

# Project-local identity wins over a differing global one.
set_global "Global Person" global@example.com
d="$(host "Local Person" local@example.com)"
out="$(init "$d")"
assert_contains "$out" '"status": "scaffolded"' "local identity: scaffolds"
assert_idents "$d" "Local Person <local@example.com>" "local identity: wiki commits carry the project's local identity"
assert_grep_file "$d/.llm-wiki/log_bar.md" "- by: Local Person via claude-code" "local identity: log by-line names the local user"
if [ "$(git -C "$d/.llm-wiki" config --local user.email)" = local@example.com ]; then
    _pass "local identity: wiki checkout keeps it for later commits"
else
    _fail "local identity: wiki checkout does not carry the project's identity"
fi
rm -rf "$d"

# Without a local identity, the global one applies.
d="$(host)"
out="$(init "$d")"
assert_contains "$out" '"status": "scaffolded"' "global identity: scaffolds"
assert_idents "$d" "Global Person <global@example.com>" "global identity: wiki commits carry the global identity"
assert_grep_file "$d/.llm-wiki/log_bar.md" "- by: Global Person via claude-code" "global identity: log by-line names the global user"
rm -rf "$d"

# An identity the wiki checkout already has is never overwritten.
d="$(host "Local Person" local@example.com)"
git -C "$d" init -q .llm-wiki
git -C "$d/.llm-wiki" config user.name "Wiki Person"
git -C "$d/.llm-wiki" config user.email wiki@example.com
out="$(init "$d")"
assert_contains "$out" '"status": "scaffolded"' "wiki identity: scaffolds"
assert_idents "$d" "Wiki Person <wiki@example.com>" "wiki identity: an existing wiki identity is kept"
rm -rf "$d"

# Environment identity is explicit and accepted.
clear_global
d="$(host)"
out="$(cd "$d" && GIT_AUTHOR_NAME="Env Person" GIT_AUTHOR_EMAIL=env@example.com \
      GIT_COMMITTER_NAME="Env Person" GIT_COMMITTER_EMAIL=env@example.com bash "$INIT" --agent claude-code 2>/dev/null)"
assert_contains "$out" '"status": "scaffolded"' "env identity: scaffolds"
assert_idents "$d" "Env Person <env@example.com>" "env identity: wiki commits carry the environment identity"
assert_grep_file "$d/.llm-wiki/log_bar.md" "- by: Env Person via claude-code" "env identity: log by-line names the environment user"
rm -rf "$d"

# No identity anywhere: stop before writing, name the problem, and recover on rerun.
d="$(host)"
out="$(init "$d")"; rc=$?
if [ "$rc" -ne 0 ]; then _pass "no identity: exits non-zero"; else _fail "no identity: exited 0"; fi
assert_contains "$out" '"status": "missing-identity"' "no identity: reports missing-identity"
assert_contains "$out" 'user.name' "no identity: message says which settings to configure"
assert_no_file "$d/.llm-wiki" "no identity: no checkout created"
git -C "$d" config user.name "Local Person"
git -C "$d" config user.email local@example.com
out="$(init "$d")"
assert_contains "$out" '"status": "scaffolded"' "no identity: rerun after configuring succeeds"
assert_idents "$d" "Local Person <local@example.com>" "no identity: rerun commits with the configured identity"
rm -rf "$d"

# An initialized wiki needs no identity to be recognized as such.
d="$(host)"
git -C "$d" init -q .llm-wiki
: > "$d/.llm-wiki/SCHEMA_bar.md"
git -C "$d/.llm-wiki" add SCHEMA_bar.md
git -C "$d/.llm-wiki" -c user.name=Seed -c user.email=seed@example.com commit -qm seed
out="$(init "$d")"
assert_contains "$out" '"status": "already-initialized"' "no identity: initialized wiki still reports already-initialized"
rm -rf "$d"

rm -f "$GIT_CONFIG_GLOBAL"
exit "$ASSERT_FAIL"
