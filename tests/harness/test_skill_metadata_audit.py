"""Metadata evidence must exclude tool reads and require both identifiers."""

import pytest

from .conversation import Conversation, TextMessage, ToolCall, ToolResult
from .skill_assertions import audit_messages, check_metadata


def test_text_only_conversation_is_auditable():
    audit_messages(Conversation(messages=[TextMessage("assistant", "metadata")]))


@pytest.mark.parametrize("conversation", [
    Conversation(messages=[TextMessage("assistant", "correct metadata")],
                 calls=[ToolCall("tool_use", "read skill")]),
    Conversation(messages=[TextMessage("assistant", "correct metadata")],
                 results=[ToolResult("tool_result", "metadata")]),
    Conversation(results=[ToolResult("tool_result", "read failed", failed=True)]),
])
def test_tool_activity_invalidates_metadata_recovery(conversation):
    """Even a correct answer cannot prove metadata delivery after a file read."""
    with pytest.raises(RuntimeError, match="tool activity"):
        audit_messages(conversation)


@pytest.mark.parametrize("conversation", [Conversation(),
    Conversation(messages=[TextMessage("user", "metadata")]),
    Conversation(messages=[TextMessage("assistant", "")])])
def test_missing_assistant_evidence_fails(conversation):
    with pytest.raises(RuntimeError, match="no assistant"):
        audit_messages(conversation)


@pytest.mark.parametrize("output,present", [
    ("", False), ("name", True), ("description", True),
    ("name description BODY", True), ("name", False), ("description", False),
])
def test_invalid_metadata_evidence_fails(output, present):
    """Removing either identifier or leaking the body turns the assertion red."""
    with pytest.raises(RuntimeError):
        check_metadata(output, "name", "description", "BODY", present)


def test_metadata_controls_require_both_identifiers_only_when_loaded():
    check_metadata("name description", "name", "description", "BODY", True)
    check_metadata("NONE", "name", "description", "BODY", False)
