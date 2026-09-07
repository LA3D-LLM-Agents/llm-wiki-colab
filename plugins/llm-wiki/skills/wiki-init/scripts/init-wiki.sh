#!/usr/bin/env bash
# Compatibility entrypoint; all initialization mechanics live beside this file.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/init-wiki.py" "$@"
