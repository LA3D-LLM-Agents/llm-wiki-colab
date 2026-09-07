"""Session context delivery requires hook evidence and excludes alternate reads."""

import pytest

from .conversation import Conversation, TextMessage, ToolCall
from .session_context import session_evidence

TOKEN = 'SESSION-' + 'a' * 32


def capture(emit):
    return {'token': TOKEN, 'emitted': emit}


def test_incoming_context_and_token_recovery_prove_delivery():
    conversation = Conversation(messages=[TextMessage('user', 'Session-start token: ' + TOKEN),
                                          TextMessage('assistant', TOKEN)])
    assert session_evidence(conversation, TOKEN, capture(True), emitted=True)['context_received']


def test_silent_hook_control_proves_absence():
    conversation = Conversation(messages=[TextMessage('assistant', 'NONE')])
    assert not session_evidence(conversation, 'NONE', capture(False), emitted=False)['context_received']


@pytest.mark.parametrize('conversation,output', [
    (Conversation(messages=[TextMessage('assistant', TOKEN)]), TOKEN),
    (Conversation(messages=[TextMessage('user', TOKEN), TextMessage('assistant', 'NONE')]), 'NONE'),
    (Conversation(messages=[TextMessage('user', TOKEN), TextMessage('assistant', TOKEN)],
                  calls=[ToolCall('Read', 'capture.json')]), TOKEN),
])
def test_echo_missing_recovery_or_file_read_invalidates_delivery(conversation, output):
    with pytest.raises(RuntimeError):
        session_evidence(conversation, output, capture(True), emitted=True)


@pytest.mark.parametrize('incoming,output', [(TOKEN, 'NONE'), ('', TOKEN)])
def test_token_leak_invalidates_silent_control(incoming, output):
    conversation = Conversation(messages=[TextMessage('user', incoming), TextMessage('assistant', output)])
    with pytest.raises(RuntimeError, match='leaked'):
        session_evidence(conversation, output, capture(False), emitted=False)


@pytest.mark.parametrize('captured', [{}, {'token': 'invalid', 'emitted': True}, capture(False)])
def test_missing_hook_evidence_or_wrong_mode_fails(captured):
    conversation = Conversation(messages=[TextMessage('user', TOKEN), TextMessage('assistant', TOKEN)])
    with pytest.raises(RuntimeError):
        session_evidence(conversation, TOKEN, captured, emitted=True)


def test_api_request_can_supply_context_omitted_from_transcript():
    transcript = Conversation(messages=[TextMessage('assistant', TOKEN)])
    request = Conversation(messages=[TextMessage('user', TOKEN)])
    evidence = session_evidence(transcript, TOKEN, capture(True), emitted=True, request_context=request)
    assert evidence['evidence'] == 'API request + transcript audit'


def test_request_assistant_echo_is_not_context_delivery():
    transcript = Conversation(messages=[TextMessage('assistant', TOKEN)])
    with pytest.raises(RuntimeError, match='incoming context'):
        session_evidence(transcript, TOKEN, capture(True), emitted=True, request_context=transcript)
