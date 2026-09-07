#!/usr/bin/env bash
# Exercise the coordinator contract against a copy of the installed plugin.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT
if python3 - <<'PY'
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    plugin = root / 'installed'
    shutil.copytree(os.environ['PLUGIN_ROOT'], plugin)
    stages = plugin / 'hooks/session-start.d'
    # A minimal stage pipeline proves numeric ordering, shared state, and stop.
    shutil.rmtree(stages)
    stages.mkdir()
    (stages / '20-second.py').write_text('def run(state):\n    state["context"].append(state["token"])\n    state["stop"] = True\n')
    (stages / '10-first.py').write_text('def run(state):\n    state["token"] = "ordered-stage-token"\n    state["warnings"].append("maintenance warning")\n')
    (stages / '30-skipped.py').write_text('raise RuntimeError("must not run")\n')
    def run():
        proc = subprocess.run(['python3', str(plugin / 'hooks/session-start.py')], cwd=root,
                              capture_output=True, text=True, check=True,
                              env=dict(os.environ, CLAUDE_PLUGIN_ROOT='/wrong/plugin'))
        assert not proc.stderr, proc.stderr
        return json.loads(proc.stdout)['hookSpecificOutput']['additionalContext']
    assert run() == 'maintenance warning\n\nordered-stage-token'
    (stages / '20-second.py').write_text('def run(state):\n    raise RuntimeError("failure")\n')
    context = run()
    assert 'maintenance warning' in context and '20-second.py failed' in context
    assert '30-skipped.py' not in context
    # An ordinary directory in the parent repository must never be oriented.
    shutil.rmtree(stages)
    shutil.copytree(Path(os.environ['PLUGIN_ROOT']) / 'hooks/session-start.d', stages)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    (root / '.llm-wiki').mkdir()
    context = run()
    assert 'not a separate Git checkout' in context
    assert 'Every wiki edit ends with a commit' not in context
    # The installed startup path repairs missing excludes for a valid wiki.
    subprocess.run(['git', 'init', '-q', str(root / '.llm-wiki')], check=True)
    exclude = root / '.git/info/exclude'
    exclude.write_bytes(b'# personal excludes without final newline')
    run()
    expected = b'# personal excludes without final newline\n/.llm-wiki/\n'
    assert exclude.read_bytes() == expected
    assert not (root / '.gitignore').exists()
    run()
    assert exclude.read_bytes() == expected
    subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', '.llm-wiki/'], check=True)
    (root / '.gitignore').write_text('!.llm-wiki/\n')
    assert 'could not ensure the local wiki ignore rule' in run()
    manifest = json.loads((plugin / 'hooks/hooks.json').read_text())
    entries = manifest['hooks']['SessionStart']
    assert len(entries) == 1 and len(entries[0]['hooks']) == 1
    assert 'session-start.py' in entries[0]['hooks'][0]['command']
PY
then
    _pass "session stages: ordered shared state, stop, failure diagnostics, installed paths, invalid attachment, single hook"
else
    _fail "session stage coordinator"
fi
exit "$ASSERT_FAIL"
