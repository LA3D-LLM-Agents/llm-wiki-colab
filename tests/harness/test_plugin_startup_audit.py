"""Reject assistant-only warnings, stale orientation, and bypassed validation."""

import pytest

from .conversation import TextMessage, ToolCall
from .plugin_startup import DIVERGED, INVALID, DIRTY, FETCH_FAILED, NO_REMOTE, startup_evidence
from .test_plugin_orientation_audit import sample


def test_fast_forward_excludes_stale_index():
    seed, output, transcript, context = sample()
    startup_evidence(transcript, context, output, seed, 'memory guidance', scenario='fast_forward', excluded_index='STALE')
    context.messages.append(TextMessage('user', 'STALE'))
    with pytest.raises(RuntimeError, match='wrong checkout'):
        startup_evidence(transcript, context, output, seed, 'memory guidance', scenario='fast_forward', excluded_index='STALE')


@pytest.mark.parametrize('scenario,warning', [('diverged', DIVERGED), ('dirty', DIRTY), ('fetch_failed', FETCH_FAILED), ('no_remote', NO_REMOTE)])
@pytest.mark.parametrize('missing', ['incoming', 'output', None])
def test_startup_requires_warning_delivery_and_recovery(missing, scenario, warning):
    seed, output, transcript, context = sample()
    if missing != 'incoming':
        context.messages.append(TextMessage('user', warning))
    if missing != 'output':
        output += '\n' + warning
    if missing:
        with pytest.raises(RuntimeError, match='warning absent'):
            startup_evidence(transcript, context, output, seed, 'memory guidance', scenario=scenario)
    else:
        assert startup_evidence(transcript, context, output, seed, 'memory guidance', scenario=scenario)['warning_received']


def test_invalid_attachment_must_stop_orientation():
    seed, output, transcript, context = sample()
    context.messages = [TextMessage('user', INVALID)]
    startup_evidence(transcript, context, INVALID, seed, 'memory guidance', scenario='invalid')
    context.messages.append(TextMessage('user', seed.index))
    with pytest.raises(RuntimeError, match='without opt-in'):
        startup_evidence(transcript, context, INVALID, seed, 'memory guidance', scenario='invalid')


def test_tool_read_cannot_supply_updated_memory():
    seed, output, transcript, context = sample()
    transcript.calls.append(ToolCall('Read', '.llm-wiki/index_orientation-probe.md'))
    with pytest.raises(RuntimeError, match='tool activity'):
        startup_evidence(transcript, context, output, seed, 'memory guidance', scenario='fast_forward')
