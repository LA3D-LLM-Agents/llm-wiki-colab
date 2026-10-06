#!/usr/bin/env bash
# tests/run.sh puts the open-handle shim on PYTHONPATH so that Python refuses
# to delete or rename a file it still has open, as Windows does. Every other
# test relies on that silently, so this one proves the shim is live in the
# interpreter under test, through both the os and pathlib entry points.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"

if [ ! -d /proc/self/fd ]; then
    echo "  skip  open-handle shim (needs /proc/self/fd)"
    exit 0
fi

probe="$(mktemp -d)"
trap 'rm -rf "$probe"' EXIT
if python3 - "$probe" <<'PY'
import os, pathlib, sys
root = pathlib.Path(sys.argv[1])
refused = 0
for name, attempt in (("a", lambda p: p.unlink()),
                      ("b", lambda p: os.replace(p, p.with_name("moved")))):
    path = root / name
    with path.open("wb"):
        try:
            attempt(path)
        except PermissionError:
            refused += 1
    # Once closed, the same file must be removable again. Without the shim
    # the attempt above already removed or moved it.
    path.unlink(missing_ok=True)
sys.exit(0 if refused == 2 else 1)
PY
then
    _pass "shim refuses unlink and replace on an open file"
else
    _fail "shim is not active in this interpreter; run this test via tests/run.sh"
fi
exit "$ASSERT_FAIL"
