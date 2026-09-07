#!/usr/bin/env python3
"""Skill body delivery; explicitly invoked, two live sessions per harness."""

import json
import sqlite3

from test_skill_metadata import main


def conversation(harness, probe, session):
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
            return records
    directory = probe / ("claude/projects" if harness == "claude" else "codex/sessions")
    files = list(directory.rglob(f"{session}.jsonl" if harness == "claude" else "*.jsonl"))
    if len(files) != 1:
        raise RuntimeError(f"expected one {harness} transcript")
    return [json.loads(line) for line in files[0].read_text().splitlines()]


def body_evidence(records, name, token, present, output):
    """Require body text on an incoming channel, never only an assistant echo."""
    if not output.strip():
        raise RuntimeError("empty model response")
    incoming = []
    channels = []
    calls = []
    for record in records:
        msg = record.get("payload", record) if record.get("type") == "response_item" else record
        msg = msg.get("message", msg)
        role = msg.get("role")
        kind = msg.get("type", "")
        content = msg.get("content", [])
        if isinstance(content, str) and content.startswith("["):
            content = json.loads(content)
        if kind in ("function_call_output", "custom_tool_call_output"):
            incoming.append(json.dumps(msg.get("output", "")))
            channels.append(kind)
        if kind in ("function_call", "custom_tool_call"):
            calls.append(json.dumps(msg))
        if role in ("user", "tool", "system", "developer"):
            incoming.append(json.dumps(content))
            channels.append(role)
        # Cursor stores tool results within assistant typed parts. Claude
        # stores Skill expansion in user messages and Read results in tool_result.
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type", "")
                if part_type in ("tool_use", "tool-call", "tool-invocation"):
                    calls.append(json.dumps(part))
                if part_type in ("tool-result", "tool_result"):
                    incoming.append(json.dumps(part))
                    channels.append(part_type)
    text = "\n".join(incoming)
    if not incoming:
        raise RuntimeError("no incoming conversation evidence")
    if present:
        if token not in output:
            raise RuntimeError("body token missing from model response")
        if f"Body-only marker: {token}" not in text:
            raise RuntimeError("no incoming skill-body token; assistant echo alone is insufficient")
    else:
        if token in text or token in output:
            raise RuntimeError("positive body token leaked into markerless control")
        if "No body marker is supplied." not in text:
            raise RuntimeError("control did not demonstrably load the markerless skill body")
    return {"body_received": True, "marker_present": present,
            "delivery_channels": sorted({channel for channel, content in zip(channels, incoming)
                                          if (f"Body-only marker: {token}" if present else
                                              "No body marker is supplied.") in content}),
            "skill_referenced_in_tool_call": any(name in call for call in calls),
            "tool_call_count": len(calls)}


def audit_body(harness, probe, session, name, token, present, output):
    return body_evidence(conversation(harness, probe, session), name, token, present, output)


if __name__ == "__main__":
    raise SystemExit(main(body_probe=True))
