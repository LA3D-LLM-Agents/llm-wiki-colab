#!/usr/bin/env bash
# L1: every hook command in every emitted hooks.json must actually be runnable.
# Derived from the manifests rather than from a hand-maintained list, so a hook
# script that is renamed, moved, or stripped of its exec bit fails here even if
# nobody remembers to update the path inventory.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT CODEX_PLUGIN_ROOT CURSOR_PLUGIN_ROOT

# python3 does the JSON walk and the shlex split (the command strings are shell
# syntax, so naive whitespace splitting would mis-read a quoted path).
results="$(LW_CLAUDE="$PLUGIN_ROOT" LW_CODEX="$CODEX_PLUGIN_ROOT" LW_CURSOR="$CURSOR_PLUGIN_ROOT" python3 - <<'PY'
import json
import os
import shlex
import shutil
from pathlib import Path

# (label, plugin root, root variable the harness expands, minimum command count)
# The count is a floor, not an equality: it exists so a walk that matches
# nothing cannot report zero assertions as success, and adding a hook later is
# a legitimate change that must not red this file.
SUBTREES = [
    ("claude", os.environ["LW_CLAUDE"], "CLAUDE_PLUGIN_ROOT", 2),
    ("codex", os.environ["LW_CODEX"], "CLAUDE_PLUGIN_ROOT", 2),
    ("cursor", os.environ["LW_CURSOR"], "CURSOR_PLUGIN_ROOT", 3),
]


def check(ok, label):
    print(("PASS " if ok else "FAIL ") + label)


def commands(node):
    """Every "command" string anywhere in the manifest.

    Claude/Codex nest them at hooks.<Event>[].hooks[].command and Cursor at
    hooks.<event>[].command; walking generically covers both dialects, and the
    per-subtree count assertion below catches a walk that finds nothing.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from commands(value)
    elif isinstance(node, list):
        for item in node:
            yield from commands(item)


for name, root, variable, expected in SUBTREES:
    manifest = Path(root) / "hooks/hooks.json"
    data = json.loads(manifest.read_text())
    found = list(commands(data))
    check(len(found) >= expected,
          f"{name} hooks.json declares at least {expected} hook commands (found {len(found)})")
    for raw in found:
        expanded = raw.replace("${" + variable + "}", root)
        label = f"{name}: {raw}"
        # An unexpanded ${...} means the manifest names a variable the harness
        # never sets, so the command runs against an empty path.
        check("${" not in expanded, f"{label} -- expands with only {variable}")
        argv = shlex.split(expanded)
        check(bool(argv), f"{label} -- splits to a non-empty argv")
        if not argv:
            continue
        interpreter = argv[0]
        check(interpreter in ("bash", "python3") or shutil.which(interpreter) is not None,
              f"{label} -- argv[0] {interpreter!r} is runnable")
        # The script being run: the first argument that points into the plugin
        # root. For a bare `bash script.sh` that is argv[1]; for a directly
        # executed hook it is argv[0] itself.
        candidates = [a for a in argv if a.startswith(root)]
        check(bool(candidates), f"{label} -- names a path inside the plugin root")
        if not candidates:
            continue
        target = Path(candidates[0])
        check(target.is_file(), f"{label} -- target {target.name} is a regular file")
        if interpreter not in ("bash", "python3"):
            # Nothing supplies an interpreter, so the kernel needs the exec bit.
            check(os.access(target, os.X_OK), f"{label} -- target {target.name} is executable")
PY
)"; rc=$?

# A crashed walk prints nothing; without this the loop below would report zero
# assertions and the file would exit 0.
if [ "$rc" -ne 0 ] || [ -z "$results" ]; then
    _fail "hook-target walk did not run (rc=$rc)"
    printf '%s\n' "$results"
    exit "$ASSERT_FAIL"
fi

while IFS= read -r line; do
    case "$line" in
        PASS\ *) _pass "${line#PASS }" ;;
        FAIL\ *) _fail "${line#FAIL }" ;;
        *) [ -n "$line" ] && _fail "unexpected hook-target output: $line" ;;
    esac
done <<< "$results"

exit "$ASSERT_FAIL"
