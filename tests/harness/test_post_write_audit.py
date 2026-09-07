"""Post-write evidence must bind delivery to a completed target write."""

import pytest

from .conversation import Conversation, TextMessage, ToolCall
from .post_write import CONTENTS, post_write_evidence

TOKEN = 'POSTWRITE-' + 'b' * 32


@pytest.fixture
def write_evidence(tmp_path):
    target = tmp_path / 'target.md'
    target.write_text(CONTENTS)
    captures = [{'token': TOKEN, 'emitted': True, 'observed': CONTENTS,
                 'payload': {'tool_name': 'Write', 'hook_event_name': 'PostToolUse',
                             'tool_input': {'file_path': str(target)}}}]
    conversation = Conversation(messages=[TextMessage('user', TOKEN), TextMessage('assistant', TOKEN)],
                                calls=[ToolCall('Write', str(target))])
    return target, captures, conversation


def test_completed_write_and_incoming_advisory_prove_delivery(write_evidence):
    target, captures, conversation = write_evidence
    assert post_write_evidence(conversation, TOKEN, captures, 'Write', target, emitted=True)['advisory_received']


@pytest.mark.parametrize('mutation', ['wrong_tool', 'before_write', 'wrong_target', 'wrong_event', 'duplicate_hook'])
def test_hook_must_identify_one_completed_target_write(write_evidence, mutation):
    target, captures, conversation = write_evidence
    if mutation == 'wrong_tool':
        captures[0]['payload']['tool_name'] = 'Read'
    elif mutation == 'before_write':
        captures[0]['observed'] = 'before probe\n'
    elif mutation == 'wrong_target':
        captures[0]['payload']['tool_input']['file_path'] = 'other.md'
    elif mutation == 'wrong_event':
        captures[0]['payload']['hook_event_name'] = 'PreToolUse'
    else:
        captures.append(captures[0])
    with pytest.raises(RuntimeError):
        post_write_evidence(conversation, TOKEN, captures, 'Write', target, emitted=True)


@pytest.mark.parametrize('mutation', ['read_capture', 'echo_only', 'missing_call', 'token_in_call'])
def test_alternate_reads_and_assistant_echoes_do_not_prove_delivery(write_evidence, mutation):
    target, captures, conversation = write_evidence
    if mutation == 'read_capture':
        conversation.calls.append(ToolCall('Read', 'capture.json'))
    elif mutation == 'echo_only':
        conversation.messages = [TextMessage('assistant', TOKEN)]
    elif mutation == 'missing_call':
        conversation.calls.clear()
    else:
        conversation.calls.append(ToolCall('Write', str(target) + TOKEN))
    with pytest.raises(RuntimeError):
        post_write_evidence(conversation, TOKEN, captures, 'Write', target, emitted=True)


def test_silent_hook_control_requires_no_advisory(write_evidence):
    target, captures, conversation = write_evidence
    captures[0]['emitted'] = False
    conversation.messages = [TextMessage('assistant', 'NONE')]
    assert not post_write_evidence(conversation, 'NONE', captures, 'Write', target, emitted=False)['advisory_received']
    conversation.messages.append(TextMessage('user', TOKEN))
    with pytest.raises(RuntimeError, match='leaked'):
        post_write_evidence(conversation, 'NONE', captures, 'Write', target, emitted=False)
