"""Select delivery evidence while retaining the transcript for tool audits."""

from dataclasses import dataclass

from .conversation import Conversation, load_claude_request


@dataclass(frozen=True)
class SessionEvidence:
    transcript: Conversation
    request_context: Conversation | None = None

    @property
    def context(self) -> Conversation:
        return self.request_context if self.request_context is not None else self.transcript

    @property
    def source(self) -> str:
        return "API request" if self.request_context is not None else "conversation record"


def load_session_evidence(harness, probe, transcript) -> SessionEvidence:
    # Claude transcripts can omit hook context. Missing API captures must fail,
    # even when the transcript or assistant response contains the expected text.
    request = load_claude_request(probe) if harness == "claude" else None
    return SessionEvidence(transcript, request)
