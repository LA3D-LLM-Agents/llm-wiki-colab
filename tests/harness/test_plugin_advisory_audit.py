"""The built advisory needs incoming evidence, not an assistant-only echo."""

import pytest

from .conversation import Conversation, TextMessage, ToolCall, ToolResult
from .plugin_advisory import ADVISORY, CONTENTS, advisory_evidence


@pytest.mark.parametrize("fault", [None, "echo_only", "orientation_only", "other_read", "not_written",
                                       "partial_advisory", "no_recovery", "non_wiki_leak"])
def test_advisory_delivery_contract(tmp_path, fault):
    target = tmp_path / "target.md"
    target.write_text(CONTENTS if fault != "not_written" else "before\n")
    transcript = Conversation(calls=[ToolCall("Write", str(target))])
    context = Conversation(results=[ToolResult("Write", ADVISORY)])
    output = ADVISORY
    if fault == "echo_only":
        context = Conversation(messages=[TextMessage("assistant", ADVISORY)])
    elif fault == "orientation_only":
        context = Conversation(messages=[TextMessage("user", "Before committing, run the Verification Gate.")])
    elif fault == "other_read":
        transcript.calls.append(ToolCall("Read", "hooks/posttooluse.sh"))
    elif fault == "partial_advisory":
        context.results = [ToolResult("Write", ADVISORY.splitlines()[0])]
    elif fault == "no_recovery":
        output = "NONE"
    kwargs = {"expected": fault != "non_wiki_leak", "evidence_source": "fixture"}
    if fault:
        with pytest.raises(RuntimeError):
            advisory_evidence(transcript, context, output, target, **kwargs)
    else:
        assert advisory_evidence(transcript, context, output, target, **kwargs)["advisory_received"]


def test_non_wiki_write_without_advisory(tmp_path):
    target = tmp_path / "target.md"
    target.write_text(CONTENTS)
    transcript = Conversation(calls=[ToolCall("Write", str(target))])
    assert not advisory_evidence(transcript, Conversation(), "NONE", target, expected=False,
                                 evidence_source="fixture")["advisory_received"]
