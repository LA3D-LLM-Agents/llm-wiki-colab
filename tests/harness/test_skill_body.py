"""An explicitly requested skill supplies its body to the model."""

import pytest

from .skill_assertions import body_evidence


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.parametrize("harness", ["codex", "claude", "cursor"])
def test_skill_body(harness, harness_run):
    """Both controls must load the body; only the positive body supplies a token."""
    run = harness_run
    prompt = (f"Load the skill {run.name}. "
              "Report its Body-only marker exactly, or NONE if it has no such marker.")
    run.make_fixture("No body marker is supplied.")
    run.start(prompt, live=True)
    for case, marker_present in (("marker_absent", False), ("marker_present", True)):
        # The positive token must not exist on disk during the negative control.
        if marker_present:
            run.replace_body(f"Body-only marker: {run.body_token}")
        run.install(case)
        output, conversation = run.session(case, prompt, plugin_loaded=True)
        run.record(case, body_evidence(conversation, run.name, run.body_token, marker_present, output))
