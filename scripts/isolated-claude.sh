#!/usr/bin/env bash
# isolated-claude.sh -- run claude with all persistent state redirected into a
# throwaway root, so the run can neither read nor write the user's real Claude
# Code state (~/.claude, ~/.claude.json, ~/.config/anthropic, anything under
# $HOME).
#
# Usage: scripts/isolated-claude.sh [claude args...]
#   All arguments pass through to claude unchanged (e.g. -p, --plugin-dir,
#   auth status).  The working directory is preserved: run it from the
#   workspace the agent should see.  Exits with claude's exit code.
#
# Environment:
#   ISOLATED_CLAUDE_ROOT
#     Use this directory as the probe root and keep it after the run for
#     inspection (caller owns removal; permissions are relaxed on exit so a
#     plain rm -rf works).  Default: mktemp under /tmp, removed on exit.
#     Pinning the root lets sequential wrapper calls share state.
#   ISOLATED_CLAUDE_AUTH
#     Credentials file to copy in.  Default: ~/.claude/.credentials.json.
#     The copy is removed on exit, including INT/TERM; a SIGKILL skips the
#     trap and strands the copy (mode 600) in the probe root.
#   ISOLATED_CLAUDE_ENV
#     Space-separated NAME=VALUE pairs applied after the wrapper's own pins
#     (values must not contain spaces).  The env scrub below removes every
#     inherited ANTHROPIC_*/CLAUDE*/... variable, so per-run levers like
#     ENABLE_CLAUDEAI_MCP_SERVERS=false must come through here, not the
#     caller's environment.
#
# State roots and leaks (probed on claude 2.1.237, 2026-08-27, strace; free
# probes only -- the authenticated-session path is covered by the canary):
#   CLAUDE_CONFIG_DIR  primary root: settings, .credentials.json, .claude.json
#                      (plus its lock/tmp/backup machinery), projects/
#                      (transcripts, auto-memory), plugins.  With it pinned,
#                      zero opens of the real ~/.claude were observed.
#   XDG_CONFIG_HOME    NOT covered by CLAUDE_CONFIG_DIR: the auth-profile
#                      system reads $XDG_CONFIG_HOME/anthropic/{active_config,
#                      configs/}, so the XDG pin is load-bearing, not hygiene.
#   HOME               everything else; all four XDG base dirs are re-pinned
#                      to their HOME-derived defaults (cursor lesson).
#
# Env scrub: inherited ANTHROPIC_*/CLAUDE*/MCP_*/OTEL_*/DISABLE_*/ENABLE_*
# variables are auth channels, provider switches, and behavior toggles that
# filesystem redirection cannot see; all are unset so the copied credentials
# file is provably the only identity.  This includes the nested-session vars
# (CLAUDECODE, CLAUDE_CODE_SESSION_ID, ...) claude sets in its own Bash
# subprocesses: transcript persistence is skipped by default when claude
# detects it is running inside another claude session, which would silently
# remove the probe's assertion surface, so the wrapper both scrubs those and
# sets CLAUDE_CODE_FORCE_SESSION_PERSISTENCE=1.  ZDOTDIR is scrubbed on the
# codex precedent; no pre-auth shell-snapshot activity was observed, so the
# authenticated-path question is open, and the scrub costs nothing.
#
# CLAUDE_CODE_PLUGIN_SEED_DIR is pinned to an empty probe-owned dir because
# it is an upstream pre-seeding surface a launcher can bake into the binary
# (local note: this machine's Nix wrapper does exactly that via --set-default,
# and when cwd is a jj repo also writes the repo's settings.local.json, so
# probe workspaces must not be jj repos).
#
# Residual, by construction:
#   - /etc/claude-code/ is probed for managed-settings.json, managed-settings.d,
#     CLAUDE.md, and a full .claude/{agents,commands,skills,rules,output-styles}
#     tree; unpinnable without root (absent on this host).
#   - /home/claude/.claude/remote/{.api_key,.oauth_token,.session_ingress_token}
#     are probed unconditionally (absent on this host).
#   - The CLAUDE.md/.claude/ walk-up checks every cwd ancestor up to /; run
#     from a workspace whose ancestors are clean.
#   - Account-side context pushed through the OAuth identity (connectors,
#     synced skills) is server-side and not starved here; conformance cells
#     pin that residual inventory instead.
#
# Wrapper defaults: CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC severs
# auto-update/telemetry/error-reporting traffic;
# OTEL_LOG_RAW_API_BODIES spools raw request/response bodies to
# $root/api-bodies as a capture byproduct (contains user identity and full
# context; never commit unredacted).

set -euo pipefail

if ! command -v claude >/dev/null 2>&1; then
  echo "isolated-claude: claude not found on PATH" >&2
  exit 127
fi

auth_src="${ISOLATED_CLAUDE_AUTH:-$HOME/.claude/.credentials.json}"
if [ ! -f "$auth_src" ]; then
  echo "isolated-claude: credentials file not found: $auth_src" >&2
  exit 1
fi

keep_root=0
if [ -n "${ISOLATED_CLAUDE_ROOT:-}" ]; then
  root="$ISOLATED_CLAUDE_ROOT"
  mkdir -p "$root"
  keep_root=1
else
  root="$(mktemp -d /tmp/claude-isolated.XXXXXX)"
fi

# shellcheck disable=SC2329  # invoked via trap
cleanup() {
  # The credentials copy never survives the run, even when the root is kept.
  rm -f "$root/claude/.credentials.json"
  chmod -R u+rwX "$root" 2>/dev/null || true
  if [ "$keep_root" -eq 0 ]; then
    rm -rf "$root"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# CLAUDE_CONFIG_DIR is kept outside the probe home on purpose: state landing
# in $root/claude proves the pin is honored, while a regression to the
# $HOME/.claude default would land in $root/home/.claude -- still inside the
# probe, and visible to the canary.
mkdir -p "$root/claude" "$root/home" "$root/plugin-seed" "$root/api-bodies"
chmod 700 "$root" "$root/claude" "$root/home"
cp "$auth_src" "$root/claude/.credentials.json"
chmod 600 "$root/claude/.credentials.json"

# Inherited env in the scrub classes above; built with compgen so multiline
# values cannot confuse the parse.
unsets=()
while IFS= read -r name; do
  case "$name" in
    ANTHROPIC_*|CLAUDE*|MCP_*|OTEL_*|DISABLE_*|ENABLE_*| \
    DO_NOT_TRACK|IS_DEMO|AWS_BEARER_TOKEN_BEDROCK|ZDOTDIR)
      unsets+=(-u "$name") ;;
  esac
done < <(compgen -e)

extra_env=()
if [ -n "${ISOLATED_CLAUDE_ENV:-}" ]; then
  # shellcheck disable=SC2206  # word splitting is the documented contract
  extra_env=($ISOLATED_CLAUDE_ENV)
fi

echo "isolated-claude: probe root: $root" >&2

rc=0
env ${unsets[@]+"${unsets[@]}"} \
  HOME="$root/home" \
  XDG_CONFIG_HOME="$root/home/.config" \
  XDG_CACHE_HOME="$root/home/.cache" \
  XDG_DATA_HOME="$root/home/.local/share" \
  XDG_STATE_HOME="$root/home/.local/state" \
  CLAUDE_CONFIG_DIR="$root/claude" \
  CLAUDE_CODE_PLUGIN_SEED_DIR="$root/plugin-seed" \
  CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1 \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  CLAUDE_CODE_FORCE_SESSION_PERSISTENCE=1 \
  OTEL_LOG_RAW_API_BODIES="file:$root/api-bodies" \
  ${extra_env[@]+"${extra_env[@]}"} \
  claude "$@" || rc=$?
exit "$rc"
