#!/usr/bin/env bash
# isolated-codex.sh -- run codex with all persistent state redirected into a
# throwaway root, so the run can neither read nor write the user's real Codex
# state (~/.codex, anything under $HOME).
#
# Usage: scripts/isolated-codex.sh [codex args...]
#   All arguments pass through to codex unchanged (e.g. exec, plugin add).
#   The working directory is preserved: run it from the workspace the agent
#   should see.  Exits with codex's exit code.
#
# Environment:
#   ISOLATED_CODEX_ROOT
#     Use this directory as the probe root and keep it after the run for
#     inspection (caller owns removal; permissions are relaxed on exit so a
#     plain rm -rf works).  Default: mktemp under /tmp, removed on exit.
#     Pinning the root lets sequential wrapper calls share state (e.g.
#     plugin add, then exec).
#   ISOLATED_CODEX_AUTH
#     Auth file to copy in.  Default: ~/.codex/auth.json.
#     The copy is removed on exit, including INT/TERM; a SIGKILL skips the
#     trap and strands the copy (mode 600) in the probe root.
#
# State roots and leaks (probed on codex-cli 0.147.0, 2026-08-27, strace):
#   CODEX_HOME   primary root: config.toml, auth.json, plugins, sessions,
#                skills, rules, AGENTS.md, history, sqlite state.  auth.json
#                is opened only at $CODEX_HOME/auth.json.  The directory must
#                exist before the run; codex hard-errors on a missing path.
#   HOME         NOT covered by CODEX_HOME: codex reads $HOME/.agents/skills
#                even with CODEX_HOME pinned, so the HOME pin is load-bearing,
#                not hygiene.  All four XDG base dirs are re-pinned to their
#                HOME-derived defaults for subprocesses (cursor lesson).
#   ZDOTDIR      an inherited ZDOTDIR pulls the user's real zsh rc into
#                codex's shell snapshot despite the pinned HOME, and a
#                sourced rc can re-export real paths into the session; unset
#                so zsh resolves under the probe home, where no rc exists.
#   OPENAI_API_KEY / CODEX_API_KEY
#                unset so the copied auth.json is provably the only identity.
#                (Probed: a dummy OPENAI_API_KEY does not register in
#                `codex login status` at 0.147.0, but an env auth path would
#                be invisible to filesystem redirection, so sever it anyway.)
#
# A fresh CODEX_HOME also starves the user's global AGENTS.md, rules/,
# skills/, memories, and config.toml (no real MCP wiring leaks in).  No
# account-side plugin sync has been observed (unlike cursor); the canary
# watches for unexpected materialization instead of starving it.
#
# Residual, by construction: codex still walks the working directory's
# ancestors for .codex-plugin/plugin.json and project AGENTS.md, and binaries
# resolve through the inherited PATH.  Run from a scratch workspace whose
# ancestors carry neither.
#
# A probe root under /tmp makes codex print "Refusing to create helper
# binaries under temporary dir" to stderr and proceed; the warning is benign,
# so assert on output content, never on stderr.

set -euo pipefail

if ! command -v codex >/dev/null 2>&1; then
  echo "isolated-codex: codex not found on PATH" >&2
  exit 127
fi

auth_src="${ISOLATED_CODEX_AUTH:-$HOME/.codex/auth.json}"
if [ ! -f "$auth_src" ]; then
  echo "isolated-codex: auth file not found: $auth_src" >&2
  exit 1
fi

keep_root=0
if [ -n "${ISOLATED_CODEX_ROOT:-}" ]; then
  root="$ISOLATED_CODEX_ROOT"
  mkdir -p "$root"
  keep_root=1
else
  root="$(mktemp -d /tmp/codex-isolated.XXXXXX)"
fi

# shellcheck disable=SC2329  # invoked via trap
cleanup() {
  # The auth copy never survives the run, even when the root is kept.
  rm -f "$root/codex/auth.json"
  chmod -R u+rwX "$root" 2>/dev/null || true
  if [ "$keep_root" -eq 0 ]; then
    rm -rf "$root"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# CODEX_HOME is kept outside the probe home on purpose: state landing in
# $root/codex proves the pin is honored, while a regression to the
# $HOME/.codex default would land in $root/home/.codex -- still inside the
# probe, and visible to the canary.
mkdir -p "$root/codex" "$root/home"
chmod 700 "$root" "$root/codex" "$root/home"
cp "$auth_src" "$root/codex/auth.json"
chmod 600 "$root/codex/auth.json"

echo "isolated-codex: probe root: $root" >&2

rc=0
env -u ZDOTDIR -u OPENAI_API_KEY -u CODEX_API_KEY \
  HOME="$root/home" \
  XDG_CONFIG_HOME="$root/home/.config" \
  XDG_CACHE_HOME="$root/home/.cache" \
  XDG_DATA_HOME="$root/home/.local/share" \
  XDG_STATE_HOME="$root/home/.local/state" \
  CODEX_HOME="$root/codex" \
  codex "$@" || rc=$?
exit "$rc"
