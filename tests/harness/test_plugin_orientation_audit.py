"""The integration assertion checks delivered state, not hook implementation."""

import pytest

from .conversation import Conversation, TextMessage, ToolCall
from .plugin_orientation import OrientationSeed, orientation_evidence


def sample():
    seed = OrientationSeed('INDEX', tuple(f'LOG-{i}' for i in range(7)), 'PAGE', 'SCHEMA-BODY')
    context = '\n'.join([*seed.expected, 'memory guidance', '.llm-wiki/SCHEMA_orientation-probe.md'])
    output = '\n'.join(seed.expected)
    transcript = Conversation(messages=[TextMessage('assistant', output)])
    request_context = Conversation(messages=[TextMessage('user', context)])
    return seed, output, transcript, request_context


def test_index_recent_logs_and_guidance_reach_model():
    seed, output, transcript, context = sample()
    result = orientation_evidence(transcript, context, output, seed, 'memory guidance', opted_in=True)
    assert result['recent_log_entries'] == 5


@pytest.mark.parametrize('missing', ['INDEX', 'LOG-2', 'LOG-6', 'memory guidance', '.llm-wiki/SCHEMA_orientation-probe.md'])
def test_missing_orientation_component_fails(missing):
    seed, output, transcript, context = sample()
    context.messages[0] = TextMessage('user', context.messages[0].text.replace(missing, ''))
    with pytest.raises(RuntimeError):
        orientation_evidence(transcript, context, output, seed, 'memory guidance', opted_in=True)


@pytest.mark.parametrize('leaked', ['LOG-0', 'LOG-1', 'PAGE', 'SCHEMA-BODY'])
def test_non_injected_wiki_contents_are_excluded(leaked):
    seed, output, transcript, context = sample()
    context.messages.append(TextMessage('user', leaked))
    with pytest.raises(RuntimeError, match='leaked'):
        orientation_evidence(transcript, context, output, seed, 'memory guidance', opted_in=True)


def test_file_read_cannot_substitute_for_orientation():
    seed, output, transcript, context = sample()
    transcript.calls.append(ToolCall('Read', '.llm-wiki/index_orientation-probe.md'))
    with pytest.raises(RuntimeError, match='tool activity'):
        orientation_evidence(transcript, context, output, seed, 'memory guidance', opted_in=True)


def test_unopted_project_gets_no_wiki_orientation():
    seed, _, _, _ = sample()
    transcript = Conversation(messages=[TextMessage('assistant', 'NONE')])
    context = Conversation(messages=[TextMessage('user', 'prompt')])
    result = orientation_evidence(transcript, context, 'NONE', seed, 'memory guidance', opted_in=False)
    assert result['index_delivered'] is False
    context.messages.append(TextMessage('user', seed.index))
    with pytest.raises(RuntimeError, match='without opt-in'):
        orientation_evidence(transcript, context, 'NONE', seed, 'memory guidance', opted_in=False)
