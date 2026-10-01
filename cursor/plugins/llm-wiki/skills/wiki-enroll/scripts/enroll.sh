#!/usr/bin/env bash
# Resolve from this installed skill, independently of harness environment variables.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v uv >/dev/null 2>&1; then
    exec uv run --script --python "$(command -v python3)" "$SCRIPT_DIR/enroll.py" "$@"
fi
exec python3 "$SCRIPT_DIR/enroll.py" "$@"
