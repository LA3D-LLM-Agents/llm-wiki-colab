#!/usr/bin/env bash
# isolated-cursor.sh -- run cursor-agent with all persistent state redirected
# into a throwaway root, so the run can neither read nor write the user's real
# Cursor state (~/.cursor, ~/.config/cursor, anything under $HOME).
#
# Usage: scripts/isolated-cursor.sh [cursor-agent args...]
#   All arguments pass through to cursor-agent unchanged (e.g. --plugin-dir).
#   The working directory is preserved: run it from the workspace the agent
#   should see.  Exits with cursor-agent's exit code.
#
# Environment:
#   ISOLATED_CURSOR_ROOT
#     Use this directory as the probe root and keep it after the run for
#     inspection (caller owns removal; permissions are relaxed on exit so a
#     plain rm -rf works).  Default: mktemp under /tmp, removed on exit.
#   ISOLATED_CURSOR_ALLOW_ACCOUNT_PLUGINS=1
#     Skip the plugins block below, letting account-installed plugins sync
#     into the run.  Default: blocked.
#   ISOLATED_CURSOR_AUTH
#     Auth file to copy in.  Default: ~/.config/cursor/auth.json.
#     The copy is removed on exit, including INT/TERM; a SIGKILL skips the
#     trap and strands the copy (mode 600) in the probe root.
#
# State roots (probed on cursor-agent 2026.08.11; auth path re-probed on
# 2026.08.25-3e8eec8):
#   CURSOR_CONFIG_DIR  CLI config and caches (cli-config.json,
#                      statsig-cache.json) and chat state, but NOT auth:
#                      strace shows auth.json is opened only at
#                      $XDG_CONFIG_HOME/cursor/auth.json, falling back to
#                      $HOME/.config/cursor/ when XDG_CONFIG_HOME is unset,
#                      so the auth copy goes under the probe home's pinned
#                      XDG config dir
#   CURSOR_DATA_DIR    projects and worker logs (a subset of ~/.cursor)
#   HOME               everything else cursor-agent drops under $HOME/.cursor
#                      (agent-cli-state, skills sync, plugin materialization)
#                      plus npm cache/log writes
# All three are required.  HOME alone is defeated by an exported absolute
# XDG_CONFIG_HOME, which keeps the real ~/.config in play; the run therefore
# re-pins all four XDG base dirs (CONFIG/CACHE/DATA/STATE) to their
# HOME-derived defaults under the probe root so inherited values cannot
# reach real state through cursor-agent or its subprocesses (npm et al.).
#
# Plugins installed on the signed-in account sync into even a fully isolated
# run and their hooks execute; the copied auth file is the account identity.
# A read-only (mode 555) $HOME/.cursor/plugins starves that materialization
# without breaking the session, while --plugin-dir still loads local plugins,
# so a candidate plugin can be injected regardless of account install state.

set -euo pipefail

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "isolated-cursor: cursor-agent not found on PATH" >&2
  exit 127
fi

auth_src="${ISOLATED_CURSOR_AUTH:-$HOME/.config/cursor/auth.json}"
if [ ! -f "$auth_src" ]; then
  echo "isolated-cursor: auth file not found: $auth_src" >&2
  exit 1
fi

keep_root=0
if [ -n "${ISOLATED_CURSOR_ROOT:-}" ]; then
  root="$ISOLATED_CURSOR_ROOT"
  mkdir -p "$root"
  keep_root=1
else
  root="$(mktemp -d /tmp/cursor-isolated.XXXXXX)"
fi

# shellcheck disable=SC2329  # invoked via trap
cleanup() {
  # The auth copy never survives the run, even when the root is kept.
  rm -f "$root/home/.config/cursor/auth.json"
  # Relax the mode-555 plugins dir so removal works either way.
  chmod -R u+rwX "$root" 2>/dev/null || true
  if [ "$keep_root" -eq 0 ]; then
    rm -rf "$root"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$root/config" "$root/data" "$root/home/.config/cursor"
chmod 700 "$root" "$root/config" "$root/data" "$root/home"
cp "$auth_src" "$root/home/.config/cursor/auth.json"
chmod 600 "$root/home/.config/cursor/auth.json"

if [ -z "${ISOLATED_CURSOR_ALLOW_ACCOUNT_PLUGINS:-}" ]; then
  mkdir -p "$root/home/.cursor/plugins"
  chmod 555 "$root/home/.cursor/plugins"
fi

echo "isolated-cursor: probe root: $root" >&2

rc=0
HOME="$root/home" \
XDG_CONFIG_HOME="$root/home/.config" \
XDG_CACHE_HOME="$root/home/.cache" \
XDG_DATA_HOME="$root/home/.local/share" \
XDG_STATE_HOME="$root/home/.local/state" \
CURSOR_CONFIG_DIR="$root/config" \
CURSOR_DATA_DIR="$root/data" \
cursor-agent "$@" || rc=$?
exit "$rc"
