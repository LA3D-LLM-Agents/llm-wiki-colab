#!/usr/bin/env bash
# Smoke test for the ported ask.sh: usage/error paths, plus one fully offline
# direct-mode resolve -> clone -> invoke against a mock federation index and a
# local wiki repo (LLM_CLI=true, so no real claude call and no network).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$HERE/lib/assert.sh"
ASK="$ROOT/core/scripts/agent-comms/ask.sh"

bash "$ASK" --help >/dev/null 2>&1 && _pass "--help exits 0" || _fail "--help nonzero"
bash "$ASK" >/dev/null 2>&1; [ $? -eq 2 ] && _pass "no args -> usage error (2)" || _fail "no-args exit not 2"

tmp="$(mktemp -d)"
wiki="$tmp/agent-wiki"; mkdir -p "$wiki"
git -C "$wiki" init -q; git -C "$wiki" config user.name t; git -C "$wiki" config user.email t@t
printf '# Index\n- Welcome\n' > "$wiki/index_demo.md"; printf '# Welcome\n' > "$wiki/Welcome.md"
git -C "$wiki" add -A; git -C "$wiki" commit -qm seed
cat > "$tmp/index.json" <<JSON
{"agents":[{"id":"demo/agent","owner_repo":"demo/agent","wiki_clone_url":"file://$wiki","description":"demo","topics":["t"]}]}
JSON
export FEDERATION_INDEX_URL="file://$tmp/index.json"
export LLM_AGENTS_DIR="$tmp/agents"
export LLM_CLI="true"

out="$(bash "$ASK" demo/agent "what do you do?" 2>&1)"; rc=$?
if [ "$rc" -eq 0 ]; then _pass "direct mode resolve+clone+invoke exits 0"; else _fail "direct mode rc=$rc"; printf '%s\n' "$out" | sed 's/^/    /'; fi
[ -d "$tmp/agents/wikis-cache/demo/agent/.git" ] && _pass "cloned the agent wiki into the cache" || _fail "cache clone missing"

bash "$ASK" demo/agent "" >/dev/null 2>&1; [ $? -eq 5 ] && _pass "empty question -> exit 5" || _fail "empty-question exit not 5"

rm -rf "$tmp"
exit "$ASSERT_FAIL"
