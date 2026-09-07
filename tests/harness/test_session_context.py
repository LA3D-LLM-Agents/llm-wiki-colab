"""Session-start hook context reaches the model without tool reads."""

import json

import pytest

from .conversation import load_claude_request
from .session_context import TOKEN, make_session_fixture, session_evidence
from .skill_assertions import audit_messages

PROMPT = "What is the session-start token? Reply with exactly the token, or NONE if none was supplied. Do not use tools."


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_session_context(harness, harness_run):
    """Suppressing hook context removes the token without suppressing execution."""
    run = harness_run
    run.start(PROMPT, live=True)
    for case, emit in (("context_absent", False), ("context_present", True)):
        capture = make_session_fixture(run, case, emit=emit)
        run.install(case)
        output, conversation = run.session(case, PROMPT, plugin_loaded=True, trust_hooks=harness == "codex")
        assert capture.is_file(), "session-start hook did not execute"
        captured = json.loads(capture.read_text())
        event = "sessionStart" if harness == "cursor" else "SessionStart"
        assert captured["payload"].get("hook_event_name") == event
        request = load_claude_request(run.root / case) if harness == "claude" else None
        run.record(case, session_evidence(conversation, output, captured, emitted=emit,
                                          request_context=request))


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.parametrize("harness", ["codex"])
def test_session_context_requires_codex_hook_trust(harness, harness_run):
    """Fresh headless state does not silently acquire plugin hook trust."""
    run = harness_run
    run.start(PROMPT, live=True)
    case = "default_trust"
    capture = make_session_fixture(run, case, emit=True)
    run.install(case)
    output, conversation = run.session(case, PROMPT, plugin_loaded=True)
    audit_messages(conversation)
    assert output.strip(), "empty model response"
    assert not capture.exists(), "hook executed without persisted trust or explicit bypass"
    assert not TOKEN.search(output)
    assert not any(TOKEN.search(text) for _, text in conversation.incoming)
    run.record(case, {"hook_executed": False, "context_received": False, "hook_trust": "default"})
