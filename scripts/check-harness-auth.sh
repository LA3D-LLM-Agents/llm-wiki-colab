#!/usr/bin/env bash
# check-harness-auth.sh -- prove each harness CLI can complete an authenticated
# model call before a live run spends anything on it.
#
# Usage: scripts/check-harness-auth.sh [claude|codex|cursor ...]
#   Default: all three.  Prints one line per harness and exits with the number
#   of harnesses that failed.  Honors ISOLATED_<HARNESS>_AUTH like the wrappers.
#
# Why a model call rather than the CLIs' own status commands:
#   codex login status   reads the file only: a `{}` auth.json prints
#                        "Logged in using ChatGPT" and exits 0.
#   claude auth status   reads the file only, so a revoked token still reports
#                        loggedIn: true.
#   cursor-agent status  does reach the server, but exits 0 on "Not logged in"
#                        and on "Logged in (unable to fetch user details)", the
#                        shape a dead refresh token produced on 2026-09-16 while
#                        every live case failed with "Authentication required".
# The failure that matters is the token refresh at first use, and only a real
# call exercises it.  Each probe runs through the isolation wrapper, so the
# file and environment validated here are the ones tests/harness copies in.
#
# Unauthenticated probes spend nothing; the shapes observed are:
#   claude 2.1.260      "Not logged in · Please run /login", exit 1
#   codex 0.153.4       "ERROR: Your access token could not be refreshed ...", exit 1
#   cursor 2026.08.25   "Error: Authentication required. Please run 'agent login' ...", exit 1
# An authenticated probe costs one short completion per harness.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROMPT='Reply with exactly the word PONG and nothing else.'
PROBE_TIMEOUT="${CHECK_HARNESS_AUTH_TIMEOUT:-180}"

if [ "$#" -eq 0 ]; then
    set -- claude codex cursor
fi

FAIL=0
for harness in "$@"; do
    case "$harness" in
        claude)
            binary=claude
            auth="${ISOLATED_CLAUDE_AUTH:-$HOME/.claude/.credentials.json}"
            remedy="claude auth login"
            args=(-p --model haiku --output-format text "$PROMPT")
            ;;
        codex)
            binary=codex
            auth="${ISOLATED_CODEX_AUTH:-$HOME/.codex/auth.json}"
            remedy="codex login"
            args=(exec --skip-git-repo-check -s read-only "$PROMPT")
            ;;
        cursor)
            binary=cursor-agent
            auth="${ISOLATED_CURSOR_AUTH:-$HOME/.config/cursor/auth.json}"
            remedy="cursor-agent login"
            args=(-p --trust --sandbox disabled --output-format text --mode ask "$PROMPT")
            ;;
        *)
            echo "  FAIL $harness: unknown harness (claude, codex, cursor)"
            FAIL=$((FAIL + 1))
            continue
            ;;
    esac

    if ! command -v "$binary" >/dev/null 2>&1; then
        echo "  FAIL $harness: $binary is not on PATH"
        FAIL=$((FAIL + 1))
        continue
    fi
    version="$("$binary" --version 2>/dev/null | head -1)"
    if [ ! -f "$auth" ]; then
        echo "  FAIL $harness $version: no credentials at $auth; run: $remedy"
        FAIL=$((FAIL + 1))
        continue
    fi

    # A scratch workspace keeps project instructions and any wiki out of the
    # probe; the wrappers preserve the working directory.
    workspace="$(mktemp -d)"
    if [ "$harness" = cursor ]; then
        args+=(--workspace "$workspace")
    fi
    output="$(cd "$workspace" && timeout "$PROBE_TIMEOUT" "$HERE/isolated-$harness.sh" "${args[@]}" </dev/null 2>&1)"
    rc=$?
    rm -rf "$workspace"

    if [ "$rc" -eq 0 ] && printf '%s' "$output" | grep -q 'PONG'; then
        echo "  ok   $harness $version: authenticated model call completed"
        continue
    fi
    # The wrapper's own probe-root line is noise; the last remaining line is
    # the CLI's error.
    reason="$(printf '%s\n' "$output" | grep -v '^isolated-' | grep -v '^[[:space:]]*$' | tail -1)"
    if [ "$rc" -eq 124 ]; then
        reason="no response within ${PROBE_TIMEOUT}s"
    fi
    echo "  FAIL $harness $version: exit $rc: ${reason:-no output}; run: $remedy"
    FAIL=$((FAIL + 1))
done

exit "$FAIL"
