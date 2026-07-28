#!/usr/bin/env bash
# Assemble the installable Cursor plugin by copying the shared neutral
# core into the adapter. The marketplace `source` is adapters/cursor, which
# must be self-contained at install time; core/ lives once at the repo root and
# is copied in here.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
rm -rf "$HERE/core"
cp -R "$ROOT/core" "$HERE/core"
echo "Copied core/ into adapters/cursor/core/ ($(find "$HERE/core" -type f | wc -l | tr -d ' ') files)."
