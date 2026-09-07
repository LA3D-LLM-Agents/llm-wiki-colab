"""Initializer state transitions, preservation, and standalone resource resolution."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
from unittest.mock import patch

with tempfile.TemporaryDirectory() as scratch:
    base = Path(scratch)
    skill = base / 'standalone skill'
    shutil.copytree(Path(os.environ['PLUGIN_ROOT']) / 'skills/wiki-init', skill)
    config = base / 'gitconfig'
    config.write_text('[user]\n name = Wiki Test\n email = wiki@example.org\n[commit]\n gpgSign = false\n')
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM='1',
               GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='Wiki Test',
               GIT_AUTHOR_EMAIL='wiki@example.org', GIT_COMMITTER_NAME='Wiki Test',
               GIT_COMMITTER_EMAIL='wiki@example.org', PYTHONDONTWRITEBYTECODE='1')
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_CONFIG_COUNT'):
        env.pop(key, None)
    # URL rewriting makes --github exercise actual ls-remote and clone, offline.
    remotes = base / 'remotes'
    remotes.mkdir()
    with config.open('a') as out:
        out.write(f'[url "{remotes.as_uri()}/"]\n insteadOf = https://github.com/test/\n')

    def git(root, *args):
        return subprocess.run(['git', '-C', str(root), *args], env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def project(name='bar'):
        root = base / f'project-{len(list(base.iterdir()))}'
        root.mkdir()
        git(root, 'init', '-q')
        git(root, 'remote', 'add', 'origin', f'https://github.com/test/{name}.git')
        git(root, 'commit', '--allow-empty', '-qm', 'host')
        return root

    def initialize(root, *args, expected=0):
        result = subprocess.run(['bash', str(skill / 'scripts/init-wiki.sh'), '--agent', 'codex', *args],
                                cwd=root, env=env, capture_output=True, text=True)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
        data = json.loads(result.stdout)
        assert data['wiki_path'] == str(root / '.llm-wiki')
        return data

    def save(wiki, files):
        for name, body in files.items():
            (wiki / name).write_text(body)
        git(wiki, 'add', '--', *files)
        git(wiki, 'commit', '-qm', 'seed')

    # Local setup is self-contained, literal title rendering, names from origin.
    root = project()
    title = 'Title & $(touch SHOULD_NOT_EXIST) {{REPO_NAME}}'
    out = initialize(root, '--name', title)
    wiki = root / '.llm-wiki'
    assert out['status'] == 'scaffolded'
    assert len(out['files']) == 6
    assert title in (wiki / 'Home_bar.md').read_text()
    assert 'via codex' in (wiki / 'log_bar.md').read_text()
    assert not (root / 'SHOULD_NOT_EXIST').exists()
    assert not any((root / p).exists() for p in ('wiki', 'CLAUDE.md', '.gitignore', 'WIKI-INDEX.md'))
    assert not git(root, 'status', '--porcelain')
    assert not git(wiki, 'status', '--porcelain')
    assert git(wiki, 'log', '-1', '--format=', '--name-only') == 'log_bar.md'
    for page in wiki.glob('*.md'):
        assert '{{REPO_NAME}}' not in page.read_text().replace(title, '')
        assert 'WIKI-INDEX' not in page.read_text()
    print('PASS: standalone skill scaffolds and commits only wiki files')

    # No-op preserves staged, unstaged, untracked files, index, HEAD, and excludes.
    (wiki / 'Home.md').write_text('Custom landing page\n')
    (wiki / 'notes.md').write_text('staged work\n')
    git(wiki, 'add', 'notes.md')
    (wiki / 'scratch.md').write_text('untracked work\n')
    head = git(wiki, 'rev-parse', 'HEAD')
    status = git(wiki, 'status', '--porcelain')
    staged = git(wiki, 'diff', '--cached')
    excludes = (root / '.git/info/exclude').read_bytes()
    assert initialize(root, '--github')['status'] == 'already-initialized'
    assert git(wiki, 'rev-parse', 'HEAD') == head
    assert git(wiki, 'status', '--porcelain') == status
    assert git(wiki, 'diff', '--cached') == staged
    assert (wiki / 'Home.md').read_text() == 'Custom landing page\n'
    assert (root / '.git/info/exclude').read_bytes() == excludes
    print('PASS: already initialized is a no-op even with local work')

    # Invalid attachments never operate on the host repository.
    root = project()
    wiki = root / '.llm-wiki'
    wiki.mkdir()
    (wiki / 'SCHEMA_bar.md').write_text('not a nested checkout\n')
    head = git(root, 'rev-parse', 'HEAD')
    excludes = (root / '.git/info/exclude').read_bytes()
    assert initialize(root, '--github', expected=1)['status'] == 'invalid-attachment'
    assert git(root, 'rev-parse', 'HEAD') == head
    assert (root / '.git/info/exclude').read_bytes() == excludes
    assert not (wiki / '.git').exists()
    print('PASS: invalid attachment leaves host repository untouched')

    # Existing checkout with no schema: scaffold only missing files, no clone.
    root = project()
    wiki = root / '.llm-wiki'
    git(root, 'init', '-q', str(wiki))
    originals = {'Home.md': 'Custom home\n', 'Home_bar.md': 'Custom navigation\n',
                 'index_bar.md': 'Custom catalog\n', 'Edge-Types.md': 'Custom vocabulary\n'}
    save(wiki, originals)
    (wiki / 'pending.md').write_text('keep\n')
    assert initialize(root, '--github', expected=1)['status'] == 'local-changes'
    assert not (wiki / 'SCHEMA_bar.md').exists()
    (wiki / 'pending.md').unlink()
    assert initialize(root, '--github')['status'] == 'scaffolded'
    assert all((wiki / name).read_text() == body for name, body in originals.items())
    assert not git(wiki, 'status', '--porcelain')
    print('PASS: missing-schema repair preserves existing pages and rejects dirty work')

    # Existing legacy schema is respected without stamping or migration.
    root = project()
    wiki = root / '.llm-wiki'
    git(root, 'init', '-q', str(wiki))
    save(wiki, {'SCHEMA.md': 'legacy conventions\n'})
    assert initialize(root, '--github')['status'] == 'already-initialized'
    assert not (wiki / 'SCHEMA_bar.md').exists()
    assert not (wiki / 'Home.md').exists()
    print('PASS: existing legacy schema is not migrated by initialization')

    # GitHub path: successful empty probe, inaccessible remote, populated clone.
    root = project('empty')
    git(remotes, 'init', '-q', '--bare', str(remotes / 'empty.wiki.git'))
    result = initialize(root, '--github', expected=1)
    assert result['status'] == 'needs-first-page' and result['setup_url'].endswith('/empty/wiki/_new'), result
    assert not (root / '.llm-wiki').exists()
    root = project('inaccessible')
    result = initialize(root, '--github', expected=1)
    assert result['status'] == 'remote-unavailable' and result['error']
    assert not (root / '.llm-wiki').exists()
    print('PASS: empty and inaccessible remotes are distinct, neither falls back locally')

    for seeded in (False, True):
        name = 'seeded' if seeded else 'unseeded'
        source = remotes / f'{name}.wiki.git'
        git(remotes, 'init', '-q', str(source))
        files = {'Home.md': 'Remote home\n', 'Source.md': 'Existing knowledge\n'}
        if seeded:
            files[f'SCHEMA_{name}.md'] = 'Existing conventions\n'
        save(source, files)
        root = project(name)
        remote_head = git(source, 'rev-parse', 'HEAD')
        result = initialize(root, '--github')
        wiki = root / '.llm-wiki'
        assert result['status'] == ('attached' if seeded else 'attached-and-scaffolded')
        assert all((wiki / name).read_text() == body for name, body in files.items())
        assert git(source, 'rev-parse', 'HEAD') == remote_head
        if seeded:
            assert git(wiki, 'rev-parse', 'HEAD') == remote_head
        else:
            assert (wiki / 'SCHEMA_unseeded.md').exists()
        assert not (root / 'wiki').exists()
        assert not git(root, 'status', '--porcelain')
        assert not git(wiki, 'status', '--porcelain')
    print('PASS: GitHub clone preserves remote content; scaffolds only without schema; never pushes')

    # Commit rejection must be visible, preserving the generated files for recovery.
    root = project()
    wiki = root / '.llm-wiki'
    git(root, 'init', '-q', str(wiki))
    save(wiki, {'Home.md': 'Existing home\n'})
    hook = wiki / '.git/hooks/pre-commit'
    hook.write_text('#!/bin/sh\necho rejected >&2\nexit 1\n')
    hook.chmod(0o755)
    before = git(wiki, 'rev-parse', 'HEAD')
    result = initialize(root, expected=1)
    assert result['status'] == 'commit-failed' and 'rejected' in result['error']
    assert (wiki / 'SCHEMA_bar.md').exists()
    assert git(wiki, 'rev-parse', 'HEAD') == before
    print('PASS: commit failure is reported as incomplete initialization')

    # Deterministic failures that cannot be reproduced with a local Git server.
    module = runpy.run_path(str(skill / 'scripts/init-wiki.py'))
    for url in ('https://github.com/owner/repo.git', 'https://github.com/owner/repo/',
                'git@github.com:owner/repo.git', 'ssh://git@github.com/owner/repo.git'):
        remote, setup = module['github_wiki_urls'](url)
        assert remote.endswith('/repo.wiki.git') and setup == 'https://github.com/owner/repo/wiki/_new'
    root = project()
    real_run = subprocess.run
    for operation in ('ls-remote', 'clone'):
        calls = []
        def failed_run(argv, **kwargs):
            calls.append(argv)
            if argv[3:4] == ['ls-remote']:
                if operation == 'clone':
                    return subprocess.CompletedProcess(argv, 0, 'hash\tHEAD\n', '')
                assert kwargs['timeout'] == module['NETWORK_TIMEOUT']
                assert kwargs['env']['GIT_TERMINAL_PROMPT'] == '0'
                raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
            if argv[3:4] == ['clone']:
                raise subprocess.CalledProcessError(128, argv, stderr='clone denied')
            return real_run(argv, **kwargs)
        with patch.object(subprocess, 'run', side_effect=failed_run):
            try:
                module['attach'](root, root / '.llm-wiki')
            except module['InitError'] as exc:
                assert exc.result['status'] == ('remote-unavailable' if operation == 'ls-remote' else 'clone-failed')
            else:
                raise AssertionError('network failure was swallowed')
        assert not (root / '.llm-wiki').exists()
        assert not any('init' in call[3:4] for call in calls)
    print('PASS: network timeout and clone failure stop without local fallback')
