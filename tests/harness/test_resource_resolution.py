"""Model-sensitive evaluation of bundled resource resolution on the first try."""

import pytest

from .plugin_install import install_fixture
from .resource_resolution import classify_resource_attempts, json_lines, make_resource_fixture, monitored_trace


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.non_deterministic
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_bundled_resource_first_attempt(harness, resource_sample, harness_run):
    """A decoy execution or failed launch remains a failure after recovery."""
    run = harness_run
    skill, filename, attempt_log, receipt_log = make_resource_fixture(run)
    run.report.update(skill.metadata)
    prompt = f"Load the skill {skill.name} and run its bundled probe."
    run.report.update({"sample": resource_sample, "scenario": "workspace_decoy",
                       "model_identity": "explicit selector; aliases may change",
                       "reference": "${CLAUDE_SKILL_DIR}" if harness == "claude" else "$SKILL_DIRECTORY"})
    run.start(prompt, live=True)
    case = "resource_execution"
    plugin_dir = install_fixture(run, case, skill.plugin)
    _, conversation = run.session(case, prompt, plugin_dir=plugin_dir, writable=True)
    skill_root = (run.root / case / "codex/plugins/cache/metadata-market/metadata-fixture/0.0.1/skills" / skill.name
                  if harness == "codex" else skill.directory)
    attempts, receipts = json_lines(attempt_log), json_lines(receipt_log)
    outcome = classify_resource_attempts(attempts, receipts, skill_root / "scripts" / filename,
                                         run.workspace, ["--probe", skill.name])
    # Nonstandard interpreters or execution mechanisms cannot silently evade
    # the monitor and produce a first-attempt pass. Keep the trace for review.
    if not monitored_trace(conversation.calls, filename, attempts):
        outcome = "infrastructure_failure"
    run.report["evaluation_outcome"] = outcome
    run.record(case, {"outcome": outcome, "launches": attempts, "receipts": receipts,
                      "expected_script": str(skill_root / "scripts" / filename)})
    assert outcome == "first_attempt_success", f"resource evaluation outcome: {outcome}"
