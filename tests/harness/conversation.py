"""Validate harness records at the boundary and expose typed conversation data."""

from dataclasses import dataclass, field
import json
import sqlite3
from typing import Literal

Role = Literal["user", "system", "developer", "assistant"]


@dataclass(frozen=True)
class TextMessage:
    role: Role
    text: str


@dataclass(frozen=True)
class ToolCall:
    channel: str
    arguments: str


@dataclass(frozen=True)
class ToolResult:
    channel: str
    text: str
    failed: bool = False


@dataclass
class Conversation:
    messages: list[TextMessage] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)

    @property
    def incoming(self) -> list[tuple[str, str]]:
        return ([(message.role, message.text) for message in self.messages
                 if message.role != "assistant"]
                + [(result.channel, result.text) for result in self.results if not result.failed])


def _mapping(value, context):
    if not isinstance(value, dict):
        raise RuntimeError(f"malformed {context}: expected object")
    return value


def _string(value, context):
    if not isinstance(value, str):
        raise RuntimeError(f"malformed {context}: expected text")
    return value


def _result(channel, payload, text) -> ToolResult:
    failed = payload.get("is_error", False)
    if not isinstance(failed, bool):
        raise RuntimeError("malformed tool result error flag")
    return ToolResult(channel, json.dumps(text), failed)


def _message(conversation: Conversation, role, content):
    if role == "tool":
        conversation.results.append(ToolResult("tool", json.dumps(content)))
        return
    if role not in ("user", "system", "developer", "assistant"):
        raise RuntimeError(f"unrecognized message role: {role}")
    if isinstance(content, str):
        conversation.messages.append(TextMessage(role, content))
        return
    if not isinstance(content, list):
        raise RuntimeError("malformed message content: expected text or parts")
    for raw in content:
        part = _mapping(raw, "conversation part")
        kind = part.get("type")
        if kind in ("text", "input_text", "output_text"):
            conversation.messages.append(TextMessage(role, _string(part.get("text"), "message text")))
        elif kind in ("tool_use", "tool-call", "tool-invocation"):
            conversation.calls.append(ToolCall(kind, json.dumps(part)))
        elif kind in ("tool_result", "tool-result"):
            # Store only result contents, so a token in call arguments cannot
            # masquerade as delivery. The two harnesses use different keys.
            key = "content" if kind == "tool_result" else "result"
            if key not in part:
                raise RuntimeError("malformed tool result: missing contents")
            conversation.results.append(_result(kind, part, part[key]))
        elif kind not in ("thinking", "redacted_thinking", "reasoning"):
            raise RuntimeError(f"unrecognized conversation part type: {kind}")


def parse_claude(records) -> Conversation:
    conversation = Conversation()
    for raw in records:
        record = _mapping(raw, "Claude record")
        if record.get("type") not in ("user", "assistant"):
            continue  # Lifecycle, progress, and summary records are not messages.
        message = _mapping(record.get("message"), "Claude message")
        _message(conversation, message.get("role", record["type"]), message.get("content"))
    return conversation


def parse_claude_request(raw) -> Conversation:
    """Read actual request messages; transcripts can omit SessionStart context."""
    request = _mapping(raw, "Claude request")
    conversation = Conversation()
    if "system" in request:
        _message(conversation, "system", request["system"])
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise RuntimeError("malformed Claude request: missing messages")
    for raw_message in messages:
        message = _mapping(raw_message, "Claude request message")
        _message(conversation, message.get("role"), message.get("content"))
    return conversation


def load_claude_request(probe) -> Conversation:
    files = list((probe / "api-bodies").glob("*.request.json"))
    if not files:
        raise RuntimeError("missing Claude request capture")
    conversation = Conversation()
    # Retries may produce more than one request for a single session.
    for file in files:
        request = parse_claude_request(json.loads(file.read_text()))
        conversation.messages.extend(request.messages)
        conversation.calls.extend(request.calls)
        conversation.results.extend(request.results)
    return conversation


def parse_codex(records) -> Conversation:
    conversation = Conversation()
    for raw in records:
        record = _mapping(raw, "Codex record")
        if record.get("type") != "response_item":
            continue  # Session metadata and event_msg duplicate/non-message data.
        item = _mapping(record.get("payload"), "Codex response item")
        kind = item.get("type")
        if kind == "message":
            _message(conversation, item.get("role"), item.get("content"))
        elif kind in ("function_call", "custom_tool_call"):
            key = "arguments" if kind == "function_call" else "input"
            conversation.calls.append(ToolCall(kind, _string(item.get(key), "Codex tool arguments")))
        elif kind in ("function_call_output", "custom_tool_call_output"):
            if "output" not in item:
                raise RuntimeError("malformed Codex tool result: missing output")
            conversation.results.append(_result(kind, item, item["output"]))
        elif kind != "reasoning":
            raise RuntimeError(f"unrecognized Codex response item: {kind}")
    return conversation


def parse_cursor(records) -> Conversation:
    conversation = Conversation()
    for raw in records:
        record = _mapping(raw, "Cursor message")
        content = record.get("content")
        if isinstance(content, str) and content.startswith("["):
            content = json.loads(content)
        _message(conversation, record.get("role"), content)
    return conversation


def load_conversation(harness, probe, session):
    if harness == "cursor":
        files = list((probe / "config/chats").rglob("store.db"))
        if len(files) != 1:
            raise RuntimeError("expected one Cursor chat store")
        with sqlite3.connect(f"file:{files[0]}?mode=ro", uri=True) as db:
            records = []
            for (data,) in db.execute("SELECT data FROM blobs"):
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                if data.startswith("{"):
                    msg = json.loads(data)
                    if "role" in msg:
                        records.append(msg)
            return parse_cursor(records)
    directory = probe / ("claude/projects" if harness == "claude" else "codex/sessions")
    files = list(directory.rglob(f"{session}.jsonl" if harness == "claude" else "*.jsonl"))
    if len(files) != 1:
        raise RuntimeError(f"expected one {harness} transcript")
    records = [json.loads(line) for line in files[0].read_text().splitlines()]
    return parse_claude(records) if harness == "claude" else parse_codex(records)


def rendered_prompt(raw):
    messages = json.loads(raw)
    if not isinstance(messages, list) or not messages:
        raise RuntimeError("expected a nonempty rendered message list")
    texts = []
    for message in messages:
        if not isinstance(message, dict) or message.get("type") != "message":
            raise RuntimeError("unrecognized rendered prompt message")
        if message.get("role") not in ("system", "developer", "user"):
            raise RuntimeError("unexpected role in pre-session prompt")
        content = message.get("content")
        if not isinstance(content, list):
            raise RuntimeError("unrecognized rendered prompt content")
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "input_text":
                raise RuntimeError("unrecognized rendered prompt part")
            if not isinstance(part.get("text"), str):
                raise RuntimeError("rendered prompt text missing or malformed")
            texts.append(part["text"])
    if not any(texts):
        raise RuntimeError("empty rendered prompt")
    return "\n".join(texts)
