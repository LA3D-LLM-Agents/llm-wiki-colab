"""Skill names and descriptions arrive without loading the skill body."""

import pytest

from .conversation import rendered_prompt
from .skill_assertions import audit_messages, check_metadata

PROMPT = (
    "Report the names and complete descriptions of available skills whose names "
    "start with metadata-probe-. Use only the skill metadata already in your "
    "context. Do not invoke skills or use any tools, including file reads. "
    "If none are available, reply NONE."
)


@pytest.mark.capability
@pytest.mark.parametrize("harness", ["codex", pytest.param("claude", marks=pytest.mark.live),
                                      pytest.param("cursor", marks=pytest.mark.live)])
def test_skill_metadata(harness, harness_run):
    """Removing the plugin must remove both metadata identifiers from evidence."""
    run = harness_run
    run.make_fixture(f"Body-only marker: {run.body_token}")
    run.start(PROMPT if harness != "codex" else None, live=harness != "codex")
    for case, plugin_loaded in (("plugin_absent", False), ("plugin_present", True)):
        if plugin_loaded:
            run.install(case)
        if harness == "codex":
            output = rendered_prompt(run.command(case, ["debug", "prompt-input"], run.root / case))
        else:
            output, conversation = run.session(case, PROMPT, plugin_loaded=plugin_loaded)
            audit_messages(conversation)
        check_metadata(output, run.name, run.description_token, run.body_token, plugin_loaded)
        run.record(case, {"metadata_present": plugin_loaded,
                          "evidence": "rendered prompt" if harness == "codex" else "recovery + no-tool audit"})
