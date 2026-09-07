"""Evidence selection must not hide missing context or transcript tool activity."""

import json

import pytest

from .conversation import Conversation, TextMessage, ToolCall
from .session_evidence import load_session_evidence


def test_claude_context_keeps_transcript_tool_audit_separate(tmp_path):
    capture = tmp_path / "api-bodies/session.request.json"
    capture.parent.mkdir()
    capture.write_text(json.dumps({"messages": [{"role": "user", "content": "hook context"}]}))
    transcript = Conversation(calls=[ToolCall("tool_use", "read a file")])
    evidence = load_session_evidence("claude", tmp_path, transcript)
    assert evidence.context.incoming == [("user", "hook context")]
    assert evidence.transcript.calls == transcript.calls
    assert evidence.source == "API request"


def test_claude_cannot_fall_back_to_transcript_when_request_is_missing(tmp_path):
    transcript = Conversation(messages=[TextMessage("user", "expected token")])
    with pytest.raises(RuntimeError, match="missing Claude request capture"):
        load_session_evidence("claude", tmp_path, transcript)


@pytest.mark.parametrize("harness", ["codex", "cursor"])
def test_native_transcript_supplies_context_without_api_capture(tmp_path, harness):
    transcript = Conversation(messages=[TextMessage("developer", "hook context")])
    evidence = load_session_evidence(harness, tmp_path, transcript)
    assert evidence.context is transcript
    assert evidence.request_context is None
    assert evidence.source == "conversation record"
