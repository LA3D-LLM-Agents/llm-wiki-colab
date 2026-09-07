#!/usr/bin/env bash
# Verify both installed implementations against real Git repositories.
set -euo pipefail
python3 - <<'PY'
import os
from pathlib import Path
import runpy
import subprocess
import tempfile

plugin = Path(os.environ['PLUGIN_ROOT'])
def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, text=True)

for implementation in ['skills/wiki-init/scripts/ensure-local-exclude.py',
                       'hooks/session-start.d/15-ensure-local-exclude.py']:
    ensure = runpy.run_path(str(plugin / implementation))['ensure_local_exclude']
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        git(root, 'init', '-q')
        exclude = root / '.git/info/exclude'
        original = b'# personal rules\r\n*.scratch\r\n!.llm-wiki/\r\n# no final newline'
        exclude.write_bytes(original)
        host_ignore = root / '.gitignore'
        host_ignore.write_bytes(b'# owned by the project\n')
        ensure(root)
        expected = original + b'\r\n/.llm-wiki/\r\n'
        assert exclude.read_bytes() == expected
        git(root, 'check-ignore', '-q', '.llm-wiki/')
        ensure(root)
        assert exclude.read_bytes() == expected
        assert host_ignore.read_bytes() == b'# owned by the project\n'
        # Equivalent patterns already covering the wiki require no rewrite.
        exclude.write_bytes(b'# local\n.llm-*/\n')
        ensure(root)
        assert exclude.read_bytes() == b'# local\n.llm-*/\n'
        # Missing file and missing .gitignore are supported.
        exclude.unlink()
        host_ignore.unlink()
        ensure(root)
        assert exclude.read_bytes() == b'/.llm-wiki/\n'
        assert not host_ignore.exists()
        # A higher-priority negation must be reported, never silently accepted.
        host_ignore.write_bytes(b'!.llm-wiki/\n')
        try:
            ensure(root)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('conflicting .gitignore went unreported')
        assert exclude.read_bytes() == b'/.llm-wiki/\n'
        assert host_ignore.read_bytes() == b'!.llm-wiki/\n'
        host_ignore.unlink()
        # An in-progress writer must be left alone.
        lock = exclude.with_name('exclude.lock')
        lock.write_bytes(b'other writer')
        try:
            ensure(root)
        except FileExistsError:
            pass
        else:
            raise AssertionError('overwrote another writer')
        assert lock.read_bytes() == b'other writer'
        lock.unlink()
        # Linked worktrees have a .git file and share the resolved exclude file.
        git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.org',
            'commit', '--allow-empty', '-qm', 'seed')
        linked = root / 'linked'
        git(root, 'worktree', 'add', '-qb', 'linked', str(linked))
        exclude.write_bytes(b'# shared excludes\n')
        ensure(linked)
        git(linked, 'check-ignore', '-q', '.llm-wiki/')
        assert exclude.read_bytes() == b'# shared excludes\n/.llm-wiki/\n'
        assert (linked / '.git').is_file()
        assert not (linked / '.gitignore').exists()
print('Local excludes: both installed implementations passed')
PY
