"""Boundary validation keeps tool inputs distinct from delivered content."""

import json
import sqlite3

import pytest

from .conversation import (
    Conversation, TextMessage, ToolCall, ToolResult, load_conversation,
    parse_claude, parse_claude_request, parse_codex, parse_cursor, rendered_prompt,
)


@pytest.mark.parametrize("parser,record", [
    (parse_claude, {"type": "assistant", "message": {"content": [{"type": "text", "text": "observed"}]}}),
    (parse_codex, {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                        "content": [{"type": "output_text", "text": "observed"}]}}),
    (parse_cursor, {"role": "assistant", "content": '[{"type":"text","text":"observed"}]'}),
])
def test_harness_text_records_produce_same_typed_message(parser, record):
    assert parser([record]) == Conversation(messages=[TextMessage("assistant", "observed")])


@pytest.mark.parametrize("parser,record", [
    (parse_claude, None), (parse_claude, {"type": "user", "message": None}),
    (parse_codex, {"type": "response_item", "payload": None}),
    (parse_codex, {"type": "response_item", "payload": {"type": "future-format"}}),
    (parse_cursor, {"role": "assistant", "content": ["malformed"]}),
    (parse_cursor, {"role": "assistant", "content": [{"type": "future-format"}]}),
    (parse_cursor, {"role": "assistant", "content": [{"type": "text", "text": None}]}),
    (parse_cursor, {"role": "unexpected", "content": "text"}),
])
def test_malformed_conversation_fails_closed(parser, record):
    with pytest.raises(RuntimeError):
        parser([record])


@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_missing_capture_cannot_prove_delivery(tmp_path, harness):
    with pytest.raises(RuntimeError, match="expected"):
        load_conversation(harness, tmp_path, "session")


@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_capture_loader_returns_typed_conversation(tmp_path, harness):
    message = {"role": "assistant", "content": [{"type": "text", "text": "observed"}]}
    if harness == "cursor":
        path = tmp_path / "config/chats/chat/store.db"
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE blobs (data BLOB)")
            db.execute("INSERT INTO blobs VALUES (?)", (json.dumps(message).encode(),))
            db.execute("INSERT INTO blobs VALUES (?)", (b"internal non-message blob",))
    else:
        record = ({"type": "assistant", "message": message} if harness == "claude" else
                  {"type": "response_item", "payload": {"type": "message", **message}})
        folder = "claude/projects/project" if harness == "claude" else "codex/sessions/date"
        path = tmp_path / folder / "session.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record) + "\n")
    assert load_conversation(harness, tmp_path, "session") == Conversation(messages=[TextMessage("assistant", "observed")])


def test_claude_failed_tool_result_keeps_failure_separate_from_text():
    conversation = parse_claude([{"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "body text", "is_error": True}]}}])
    assert conversation.results == [ToolResult("tool_result", '"body text"', failed=True)]
    assert conversation.incoming == []


@pytest.mark.parametrize("kind,key", [("function_call", "arguments"), ("custom_tool_call", "input")])
def test_codex_tool_arguments_are_not_incoming_content(kind, key):
    conversation = parse_codex([{"type": "response_item", "payload": {"type": kind, key: "token"}}])
    assert conversation.calls == [ToolCall(kind, "token")]
    assert conversation.incoming == []


@pytest.mark.parametrize("kind", ["function_call_output", "custom_tool_call_output"])
def test_codex_tool_outputs_become_results(kind):
    conversation = parse_codex([{"type": "response_item", "payload": {"type": kind,
                                   "output": [{"type": "input_text", "text": "body text"}]}}])
    assert conversation.results == [ToolResult(kind, '[{"type": "input_text", "text": "body text"}]')]


def test_cursor_result_does_not_include_argument_metadata():
    conversation = parse_cursor([{"role": "assistant", "content": [
        {"type": "tool-result", "result": "body text", "args": "not delivered"}]}])
    assert conversation.results == [ToolResult("tool-result", '"body text"')]


def test_prompt_evidence_excludes_record_metadata():
    raw = json.dumps([{"type": "message", "role": "developer", "metadata": "not evidence",
                       "content": [{"type": "input_text", "text": "actual evidence"}]}])
    assert rendered_prompt(raw) == "actual evidence"


@pytest.mark.parametrize("raw", ["[]", "{}", "[{}]", json.dumps([
    {"type": "message", "role": "developer", "content": [{"type": "input_text"}]}])])
def test_malformed_rendered_prompt_fails_closed(raw):
    with pytest.raises(RuntimeError):
        rendered_prompt(raw)


def test_claude_request_context_excludes_diagnostics_and_tool_definitions():
    conversation = parse_claude_request({
        'system': [{'type': 'text', 'text': 'system context'}],
        'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'hook context'}]}],
        'tools': [{'description': 'not delivered as session context'}],
        'diagnostics': {'text': 'not evidence'},
    })
    assert conversation.incoming == [('system', 'system context'), ('user', 'hook context')]


@pytest.mark.parametrize('captured_request', [{}, {'messages': []}, {'messages': [None]}])
def test_missing_claude_request_messages_fail_closed(captured_request):
    with pytest.raises(RuntimeError):
        parse_claude_request(captured_request)
