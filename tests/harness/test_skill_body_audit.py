"""Body evidence must arrive on an incoming channel, not only in an answer."""

import pytest

from .conversation import Conversation, TextMessage, ToolCall, ToolResult
from .skill_assertions import body_evidence


@pytest.mark.parametrize("conversation", [
    Conversation(messages=[TextMessage("user", "Body-only marker: BODY-secret")]),
    Conversation(results=[ToolResult("tool-result", "Body-only marker: BODY-secret")]),
])
def test_incoming_body_supports_recovery(conversation):
    evidence = body_evidence(conversation, "probe", "BODY-secret", True, "BODY-secret")
    assert evidence["body_received"] is True
    assert evidence["delivery_channels"]


@pytest.mark.parametrize("conversation", [
    Conversation(messages=[TextMessage("assistant", "Body-only marker: BODY-secret")]),
    Conversation(calls=[ToolCall("tool-call", "Body-only marker: BODY-secret")]),
    Conversation(results=[ToolResult("tool_result", "Body-only marker: BODY-secret", failed=True)]),
])
def test_echo_arguments_and_failed_results_do_not_prove_delivery(conversation):
    with pytest.raises(RuntimeError, match="no incoming"):
        body_evidence(conversation, "probe", "BODY-secret", True, "BODY-secret")


@pytest.mark.parametrize("content", ["Skill unavailable", "Body-only marker: BODY-secret"])
def test_missing_body_or_token_leak_invalidates_control(content):
    with pytest.raises(RuntimeError):
        body_evidence(Conversation(results=[ToolResult("tool", content)]),
                      "probe", "BODY-secret", False, "NONE")


def test_markerless_control_requires_incoming_body():
    body_evidence(Conversation(results=[ToolResult("tool", "No body marker is supplied.")]),
                  "probe", "BODY-secret", False, "NONE")


@pytest.mark.parametrize("output", ["NONE", ""])
def test_body_delivery_without_recovery_fails(output):
    with pytest.raises(RuntimeError):
        body_evidence(Conversation(results=[ToolResult("tool", "Body-only marker: BODY-secret")]),
                      "probe", "BODY-secret", True, output)


def test_failed_read_without_body_does_not_prove_delivery():
    with pytest.raises(RuntimeError, match="no incoming skill-body"):
        body_evidence(Conversation(results=[ToolResult("tool", "Error: file not found")]),
                      "probe", "BODY-secret", True, "BODY-secret")
