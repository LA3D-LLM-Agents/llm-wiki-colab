#!/usr/bin/env bash
# Assemble the installable Claude Code plugin by copying the shared neutral
# core into the adapter. The marketplace `source` is adapters/claude-code, which
# must be self-contained at install time; core/ lives once at the repo root and
# is copied in here (and is gitignored inside the adapter).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
rm -rf "$HERE/core"
cp -R "$ROOT/core" "$HERE/core"
echo "Copied core/ into adapters/claude-code/core/ ($(find "$HERE/core" -type f | wc -l | tr -d ' ') files)."
