"""The installed built plugin delivers project orientation across harnesses."""

import subprocess

import pytest

from .conversation import load_claude_request
from .plugin_install import install_built_plugin
from .plugin_orientation import OrientationSeed, orientation_evidence, seed_wiki

PROMPT = "List all ORIENT- tokens already present in your context, one per line. If none are present, reply NONE. Do not use tools."


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_installed_plugin_orientation(harness, harness_run, built_marketplace):
    """Opt-in delivers the index and recent log slice without reading wiki files."""
    run = harness_run
    run.start(PROMPT, live=True)
    run.report["artifact_version"] = (built_marketplace / "VERSION").read_text().strip()
    plugin = built_marketplace / harness / "plugins/llm-wiki"
    guidance = (plugin / "core/templates/guidance.md").read_text()
    subprocess.run(["git", "init", "-q", str(run.workspace)], check=True)
    subprocess.run(["git", "-C", str(run.workspace), "remote", "add", "origin",
                    "https://github.com/fixture/orientation-probe.git"], check=True)
    (run.workspace / ".gitignore").write_text(".llm-wiki/\n")
    seed = OrientationSeed.fresh()
    for case, opted_in in (("unopted", False), ("opted_in", True)):
        if opted_in:
            seed_wiki(run.workspace, seed)
        probe = run.root / case
        install_built_plugin(run, case, built_marketplace)
        # The plugin is already installed; do not inject a --plugin-dir override.
        output, transcript = run.session(case, PROMPT, trust_hooks=harness == "codex")
        request = load_claude_request(probe) if harness == "claude" else transcript
        source = "API request" if harness == "claude" else "conversation record"
        run.record(case, orientation_evidence(transcript, request, output, seed, guidance,
                                               opted_in=opted_in, evidence_source=source))
