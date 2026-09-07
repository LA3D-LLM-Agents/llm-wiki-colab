"""An explicitly requested skill supplies its body to the model."""

import pytest

from .plugin_fixture import SkillFixture
from .plugin_install import install_fixture
from .skill_assertions import body_evidence


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.parametrize("harness", ["codex", "claude", "cursor"])
def test_skill_body(harness, harness_run):
    """Both controls must load the body; only the positive body supplies a token."""
    run = harness_run
    skill = SkillFixture.create(run.root, harness)
    run.report.update(skill.metadata)
    prompt = (f"Load the skill {skill.name}. "
              "Report its Body-only marker exactly, or NONE if it has no such marker.")
    skill.replace_body("No body marker is supplied.")
    run.start(prompt, live=True)
    for case, marker_present in (("marker_absent", False), ("marker_present", True)):
        # The positive token must not exist on disk during the negative control.
        if marker_present:
            skill.replace_body(f"Body-only marker: {skill.body_token}")
        plugin_dir = install_fixture(run, case, skill.plugin)
        output, conversation = run.session(case, prompt, plugin_dir=plugin_dir)
        run.record(case, body_evidence(conversation, skill.name, skill.body_token, marker_present, output))
