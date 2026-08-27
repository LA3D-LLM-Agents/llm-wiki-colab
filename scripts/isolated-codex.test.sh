#!/usr/bin/env bash
# isolated-codex.test.sh -- canary for the facts scripts/isolated-codex.sh
# is built on, so a new codex release that changes them is caught here rather
# than in a confusing conformance-test failure.
#
# Fabricates a minimal marketplace-plus-plugin, drives it through the wrapper
# with a pinned probe root, and checks:
#   1. plugin install lands in the redirected CODEX_HOME, keyed on version,
#   2. the installed skill reaches the model-visible prompt (with a built-in
#      red: the same grep must find nothing before the install),
#   3. no state fell back to $HOME/.codex inside the probe (the CODEX_HOME
#      pin held for every subprocess),
#   4. nothing was written to the real ~/.codex,
#   5. the auth copy does not survive the run,
#   6. an exec-mode session authenticates via the copied auth.json and its
#      rollout lands under the probe CODEX_HOME.
#
# Checks 1-5 are free (`codex debug prompt-input` renders the prompt locally
# with no auth and no spend); check 6 spends one real codex model call.
# Needs codex on PATH and a signed-in account; exits 0 with a skip message
# when either is missing.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! command -v codex >/dev/null 2>&1; then
    echo "skip: codex not on PATH"
    exit 0
fi
if [ ! -f "${ISOLATED_CODEX_AUTH:-$HOME/.codex/auth.json}" ]; then
    echo "skip: no codex auth file"
    exit 0
fi
echo "codex version: $(codex --version 2>/dev/null | head -1)"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $1"; }

scratch="$(mktemp -d)"
probe="$scratch/probe"
# shellcheck disable=SC2329  # invoked via trap
cleanup() {
    chmod -R u+rwX "$scratch" 2>/dev/null || true
    rm -rf "$scratch"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Minimal marketplace carrying one plugin with one skill.  metadata is
# omitted on purpose: codex drops a skill whose metadata is a scalar
# (probed, codex-cli 0.147.0), and the canary must not depend on that quirk.
market="$scratch/canary-marketplace"
plugin="$market/codex-canary"
mkdir -p "$market/.agents/plugins" "$plugin/.codex-plugin" "$plugin/skills/canary-probe"
cat > "$market/.agents/plugins/marketplace.json" <<'EOF'
{
  "name": "isolated-codex-canary",
  "plugins": [
    {
      "name": "codex-canary",
      "source": { "source": "local", "path": "./codex-canary" },
      "description": "Throwaway canary plugin for isolated-codex.sh."
    }
  ]
}
EOF
cat > "$plugin/.codex-plugin/plugin.json" <<'EOF'
{
  "name": "codex-canary",
  "version": "0.0.1",
  "description": "Throwaway canary plugin for isolated-codex.sh."
}
EOF
cat > "$plugin/skills/canary-probe/SKILL.md" <<'EOF'
---
name: canary-probe
description: Inert canary skill; never invoke.
---
Inert.
EOF

workspace="$scratch/workspace"
mkdir -p "$workspace"
marker="$scratch/marker"
touch "$marker"
sleep 1

wrapped() {
    (cd "$workspace" && ISOLATED_CODEX_ROOT="$probe" "$HERE/isolated-codex.sh" "$@" </dev/null 2>>"$scratch/wrapper-stderr.log")
}

# Built-in red for the visibility detector: before the install, the skill
# must be absent from the rendered prompt, or the post-install grep proves
# nothing.
pre="$(wrapped debug prompt-input | grep -c 'codex-canary:canary-probe')"
if [ "$pre" -eq 0 ]; then
    ok "skill absent before install (visibility detector can go red)"
else
    bad "skill visible before install; visibility check is vacuous"
fi

wrapped plugin marketplace add "$market" >/dev/null
wrapped plugin add codex-canary@isolated-codex-canary >/dev/null

if [ -d "$probe/codex/plugins/cache/isolated-codex-canary/codex-canary/0.0.1" ]; then
    ok "install cache landed in redirected CODEX_HOME, keyed on version"
else
    bad "install cache missing from $probe/codex/plugins/cache (found: $(find "$probe/codex/plugins" -maxdepth 4 2>/dev/null | tail -3 | tr '\n' ' '))"
fi

if wrapped debug prompt-input | grep -q 'codex-canary:canary-probe'; then
    ok "installed skill reaches the model-visible prompt"
else
    bad "installed skill not in prompt-input output"
fi

# CODEX_HOME sits outside the probe home on purpose; anything under
# $HOME/.codex means some subprocess fell back to the default.
if [ ! -e "$probe/home/.codex" ]; then
    ok "nothing fell back to \$HOME/.codex inside the probe"
else
    bad "state fell back to probe \$HOME/.codex: $(find "$probe/home/.codex" -maxdepth 2 | head -3 | tr '\n' ' ')"
fi

if [ ! -e "$probe/codex/auth.json" ]; then
    ok "auth copy did not survive the run"
else
    bad "auth copy survived in probe root"
fi

real_writes="$(find "$HOME/.codex" -newer "$marker" 2>/dev/null)"
if [ -z "$real_writes" ]; then
    ok "no writes to real codex state"
else
    bad "real codex state touched: $(echo "$real_writes" | head -3 | tr '\n' ' ')"
fi

# The same predicate must fire on the probe root, or the check above is
# vacuous (a detector that has never gone red proves nothing).
if [ -n "$(find "$probe" -newer "$marker" 2>/dev/null | head -1)" ]; then
    ok "write detector fires on probe root"
else
    bad "write detector saw nothing in probe root; isolation check is vacuous"
fi

# The one model call: copied-auth exec, rollout as the record surface.
last="$scratch/last-message.txt"
wrapped exec --skip-git-repo-check -s read-only -o "$last" \
    'Reply with exactly: OK' >/dev/null
rc=$?
if [ "$rc" -eq 0 ]; then ok "exec session exit 0"; else bad "exec session exit $rc: $(tail -2 "$scratch/wrapper-stderr.log" | tr '\n' ' ')"; fi

if grep -q 'OK' "$last" 2>/dev/null; then
    ok "exec authenticated via copied auth and replied"
else
    bad "no OK in exec last message: $(head -c 120 "$last" 2>/dev/null || echo '<missing>')"
fi

if [ -n "$(find "$probe/codex/sessions" -name '*.jsonl' 2>/dev/null | head -1)" ]; then
    ok "session rollout landed under probe CODEX_HOME"
else
    bad "no rollout under $probe/codex/sessions"
fi

echo "pass=$PASS fail=$FAIL"
exit "$FAIL"
