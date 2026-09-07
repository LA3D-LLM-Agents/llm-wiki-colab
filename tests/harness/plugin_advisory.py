"""Evidence for the installed plugin's wiki-write reminder."""

from .conversation import Conversation

# Distinguishes the post-write reminder from the Verification Gate guidance
# already delivered at SessionStart. Keep this independent of hook execution.
ADVISORY = """A wiki page was just written or edited. Before committing in the wiki
repo, run the Verification Gate (core/agents/verification-gate.md in the
llm-wiki plugin) over every page created or edited this session: every
numerical claim tagged with its corpus, every projection marked as such,
back-references bidirectional, and the index plus log updated. This is an
advisory reminder and does not block."""
PREFIX = "A wiki page was just written or edited."
CONTENTS = "after advisory probe\n"


def normalize(text):
    # Native tool results can contain JSON-encoded newlines.
    return " ".join(text.replace("\\n", " ").split())


def advisory_evidence(transcript: Conversation, context: Conversation, output, target, *, expected,
                      evidence_source):
    if not target.is_file() or target.read_text() != CONTENTS:
        raise RuntimeError("requested write did not complete")
    if not output.strip():
        raise RuntimeError("empty model response")
    if not transcript.calls:
        raise RuntimeError("no recorded target tool invocation")
    if any(target.name not in call.arguments for call in transcript.calls):
        raise RuntimeError("tool activity beyond the requested target")
    if any(PREFIX in call.arguments for call in transcript.calls):
        raise RuntimeError("advisory supplied through tool arguments")
    incoming = normalize("\n".join(text for _, text in context.incoming))
    if expected:
        if normalize(ADVISORY) not in incoming:
            raise RuntimeError("installed plugin advisory absent from incoming context")
        quoted = "\n".join(line.removeprefix("> ") for line in output.splitlines())
        if normalize(ADVISORY) not in normalize(quoted):
            raise RuntimeError("installed plugin advisory not recovered")
    elif PREFIX in incoming or PREFIX in output:
        raise RuntimeError("wiki advisory delivered for a non-wiki target")
    return {"write_completed": True, "advisory_received": expected,
            "evidence": f"{evidence_source} + recovery + target tool audit"}
