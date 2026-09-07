"""Installed coordinator executes validation/update before delivering orientation."""

import pytest

from .plugin_install import install_built_plugin
from .plugin_orientation import OrientationSeed
from .plugin_startup import git, seed_remote_wiki, startup_evidence
from .session_evidence import load_session_evidence

PROMPT = ("List all ORIENT- tokens already present in your context, one per line. "
          "Also quote any wiki startup or attachment warning supplied in your context verbatim. "
          "If neither is present, reply NONE. Do not use tools.")


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
@pytest.mark.parametrize("scenario", ["fast_forward", "diverged", "invalid", "dirty", "fetch_failed", "no_remote"])
def test_installed_plugin_startup(harness, scenario, harness_run, built_marketplace):
    run = harness_run
    run.start(PROMPT, live=True)
    run.report["artifact_version"] = (built_marketplace / "VERSION").read_text().strip()
    git(run.workspace, "init", "-q")
    git(run.workspace, "remote", "add", "origin", "https://github.com/fixture/orientation-probe.git")
    (run.workspace / ".gitignore").write_text(".llm-wiki/\n")
    wiki = run.workspace / ".llm-wiki"
    if scenario == "invalid":
        wiki.mkdir()
        expected = OrientationSeed.fresh()
        # A parent Git repository must not validate this ordinary directory.
        (wiki / "index_orientation-probe.md").write_text(expected.index)
        excluded = None
    else:
        initial, updated, before, remote_tip = seed_remote_wiki(
            run.root, run.workspace, diverged=scenario == "diverged")
        assert before != remote_tip
        assert not git(wiki, "status", "--porcelain")
        expected = updated if scenario == "fast_forward" else initial
        excluded = initial.index if scenario == "fast_forward" else updated.index
        fetched_before = git(wiki, "rev-parse", "origin/main")
        if scenario == "dirty":
            (wiki / "local-draft.md").write_text("preserve this unfinished memory\n")
        elif scenario == "fetch_failed":
            git(wiki, "remote", "set-url", "origin", str(run.root / "missing-remote.git"))
        elif scenario == "no_remote":
            git(wiki, "remote", "remove", "origin")
    install_built_plugin(run, scenario, built_marketplace)
    output, transcript = run.session(scenario, PROMPT, trust_hooks=harness == "codex")
    evidence = load_session_evidence(harness, run.root / scenario, transcript)
    plugin = built_marketplace / harness / "plugins/llm-wiki"
    result = startup_evidence(evidence.transcript, evidence.context, output, expected,
                             (plugin / "core/templates/guidance.md").read_text(),
                             scenario=scenario, excluded_index=excluded,
                             evidence_source=evidence.source)
    if scenario != "invalid":
        after = git(wiki, "rev-parse", "HEAD")
        assert after == (remote_tip if scenario == "fast_forward" else before)
        if scenario != "no_remote":
            assert git(wiki, "rev-parse", "origin/main") == (
                remote_tip if scenario in ("fast_forward", "diverged") else fetched_before)
        if scenario == "dirty":
            assert (wiki / "local-draft.md").read_text() == "preserve this unfinished memory\n"
        else:
            assert not git(wiki, "status", "--porcelain")
        result.update(before=before, after=after, remote_tip=remote_tip)
    run.record(scenario, result)
