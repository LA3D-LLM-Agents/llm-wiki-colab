"""Failures before script startup and subsequent recovery remain observable."""

import json
from pathlib import Path
import subprocess

import pytest

from .conversation import ToolCall
from .harness_support import HarnessRun
from .resource_resolution import classify_resource_attempts, json_lines, make_resource_fixture, monitored_trace


def evidence(tmp_path, identity='intended', attempt='1'):
    script = tmp_path / 'skill/scripts/probe.py'
    launch = {'id': attempt, 'argv': [str(script), '--probe', 'name'], 'cwd': str(tmp_path)}
    receipt = {'attempt': attempt, 'identity': identity, 'path': str(script),
               'argv': ['--probe', 'name'], 'cwd': str(tmp_path)}
    return script, launch, receipt


def test_first_correct_execution_passes(tmp_path):
    script, launch, receipt = evidence(tmp_path)
    assert classify_resource_attempts([launch], [receipt], script, tmp_path, ['--probe', 'name']) == 'first_attempt_success'


@pytest.mark.parametrize('first', ['missing_file', 'decoy', 'wrong_args', 'wrong_cwd'])
def test_recovery_never_erases_the_first_failure(tmp_path, first):
    script, launch, receipt = evidence(tmp_path)
    bad = {**launch, 'id': '0'}
    if first in ('missing_file', 'decoy'):
        bad['argv'] = ['scripts/probe.py', '--probe', 'name']
    elif first == 'wrong_args':
        bad['argv'] = [str(script)]
    else:
        bad['cwd'] = str(tmp_path / 'elsewhere')
    bad_receipts = [] if first == 'missing_file' else [{**receipt, 'attempt': '0', 'identity': 'decoy'}]
    assert classify_resource_attempts([bad, launch], [*bad_receipts, receipt], script, tmp_path, ['--probe', 'name']) == 'recovered'


def test_receipt_without_observed_launch_is_infrastructure_failure(tmp_path):
    script, _, receipt = evidence(tmp_path)
    assert classify_resource_attempts([], [receipt], script, tmp_path, []) == 'infrastructure_failure'


@pytest.mark.parametrize('command', ['python3 scripts/probe.py', 'python3 "$SKILL_DIRECTORY/scripts/probe.py"'])
def test_simple_launch_is_auditable(command):
    calls = [ToolCall('tool_use', json.dumps({'input': {'command': command}}))]
    assert monitored_trace(calls, 'probe.py', [{}])


@pytest.mark.parametrize('command', ['cat scripts/probe.py', '/usr/bin/python3 scripts/probe.py',
                                   'python3 scripts/probe.py || python3 correct/probe.py'])
def test_unobserved_or_compound_execution_cannot_pass(command):
    calls = [ToolCall('tool_use', json.dumps({'input': {'command': command}}))]
    assert not monitored_trace(calls, 'probe.py', [{}])


def test_failed_launch_and_decoy_are_logged_before_correct_execution(tmp_path):
    """A missing script leaves no receipt, so launch logging must precede exec."""
    run = HarnessRun(tmp_path, 'claude', tmp_path / 'unused-auth', None)
    filename, attempts, receipts = make_resource_fixture(run)
    correct = run.plugin / 'skills' / run.name / 'scripts' / filename
    for script in (Path('missing') / filename, Path('scripts') / filename, correct):
        subprocess.run(['python3', str(script), '--probe', run.name], env=run.env, cwd=run.workspace,
                       capture_output=True, check=False)
    launches, executed = json_lines(attempts), json_lines(receipts)
    assert len(launches) == 3
    assert [r['identity'] for r in executed] == ['decoy', 'intended']
    assert classify_resource_attempts(launches, executed, correct, run.workspace, ['--probe', run.name]) == 'recovered'
