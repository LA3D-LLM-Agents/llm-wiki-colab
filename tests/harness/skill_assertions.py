"""Delivery invariants shared by capability probes and offline audit tests."""

from .conversation import Conversation

def audit_messages(conversation: Conversation):
    if conversation.calls or conversation.results:
        raise RuntimeError("tool activity in conversation; metadata-only proof invalid")
    if not any(message.role == "assistant" and message.text for message in conversation.messages):
        raise RuntimeError("no assistant messages available for tool-use audit")


def body_evidence(conversation: Conversation, name, token, present, output):
    """A response token alone cannot establish incoming skill-body delivery."""
    if not output.strip():
        raise RuntimeError("empty model response")
    incoming = conversation.incoming
    if not incoming:
        raise RuntimeError("no incoming conversation evidence")
    text = "\n".join(text for _, text in incoming)
    expected = f"Body-only marker: {token}" if present else "No body marker is supplied."
    if present:
        if token not in output:
            raise RuntimeError("body token missing from model response")
        if expected not in text:
            raise RuntimeError("no incoming skill-body token; assistant echo alone is insufficient")
    else:
        if token in text or token in output:
            raise RuntimeError("positive body token leaked into markerless control")
        if expected not in text:
            raise RuntimeError("control did not demonstrably load the markerless skill body")
    calls = conversation.calls
    return {"body_received": True, "marker_present": present,
            "delivery_channels": sorted({channel for channel, text in incoming if expected in text}),
            "skill_referenced_in_tool_call": any(name in call.arguments for call in calls),
            "tool_call_count": len(calls)}

def check_metadata(output, name, token, body, installed):
    if not output.strip():
        raise RuntimeError("empty evidence")
    if body in output:
        raise RuntimeError("skill body appeared; metadata-only boundary not established")
    if installed:
        if name not in output or token not in output:
            raise RuntimeError("name or description marker missing")
    elif name in output or token in output:
        raise RuntimeError("fixture metadata appeared without plugin loaded")

