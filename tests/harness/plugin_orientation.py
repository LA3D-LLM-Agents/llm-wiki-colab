"""Seed project memory and check the built plugin's orientation contract."""

from dataclasses import dataclass
import secrets
import subprocess

from .conversation import Conversation
from .skill_assertions import audit_messages


@dataclass(frozen=True)
class OrientationSeed:
    index: str
    logs: tuple[str, ...]
    page: str
    schema: str

    @classmethod
    def fresh(cls):
        def token(kind):
            return f"ORIENT-{kind}-" + secrets.token_hex(16)
        return cls(token("INDEX"), tuple(token("LOG") for _ in range(7)), token("PAGE"), token("SCHEMA"))

    @property
    def expected(self):
        return (self.index, *self.logs[-5:])

    @property
    def excluded(self):
        return (*self.logs[:-5], self.page, self.schema)


def seed_wiki(workspace, seed):
    wiki = workspace / ".llm-wiki"
    wiki.mkdir()
    subprocess.run(["git", "init", "-q", str(wiki)], check=True)
    # Uncommitted local seed content makes the update hook leave the wiki alone.
    # No wiki remote or network dependency is needed to test orientation.
    (wiki / "index_orientation-probe.md").write_text(f"# Index\n\n- [[probe-page]]: {seed.index}\n")
    (wiki / "log_orientation-probe.md").write_text("# Log\n\n" + "\n".join(
        f"## [2026-01-{i:02d}] Seeded entry\n{token}\n" for i, token in enumerate(seed.logs, 1)))
    (wiki / "probe-page.md").write_text(f"# Probe page\n\n{seed.page}\n")
    (wiki / "SCHEMA_orientation-probe.md").write_text(f"# Schema\n\n{seed.schema}\n")


def orientation_evidence(transcript: Conversation, request: Conversation, output, seed, guidance, *, opted_in,
                         evidence_source="API request"):
    audit_messages(transcript)
    if request.calls or request.results:
        raise RuntimeError("orientation request contains tool activity")
    if not output.strip():
        raise RuntimeError("empty model response")
    context = "\n".join(text for _, text in request.incoming)
    if opted_in:
        for token in seed.expected:
            if token not in context or token not in output:
                raise RuntimeError("index or recent log entry missing from delivered orientation")
        if not guidance.strip() or guidance.strip() not in context:
            raise RuntimeError("shipped memory guidance missing from model context")
        if ".llm-wiki/SCHEMA_orientation-probe.md" not in context:
            raise RuntimeError("orientation missing the namespaced schema reference")
    else:
        if any(token in context or token in output for token in seed.expected):
            raise RuntimeError("wiki state delivered without opt-in")
        if guidance.strip() in context:
            raise RuntimeError("wiki guidance delivered without opt-in")
    if any(token in context or token in output for token in seed.excluded):
        raise RuntimeError("older logs, page body, or schema body leaked into orientation")
    return {"opted_in": opted_in, "index_delivered": opted_in,
            "recent_log_entries": 5 if opted_in else 0, "guidance_delivered": opted_in,
            "tool_use": False, "evidence": f"{evidence_source} + recovery + transcript audit"}
