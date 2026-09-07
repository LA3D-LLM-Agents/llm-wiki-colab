"""Built-plugin advisory delivery after creating and updating wiki pages."""

import subprocess

import pytest

from .plugin_advisory import CONTENTS, advisory_evidence
from .plugin_install import install_built_plugin
from .plugin_orientation import OrientationSeed, seed_wiki
from .session_evidence import load_session_evidence


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
@pytest.mark.parametrize("operation", ["create", "update"])
def test_installed_plugin_write_advisory(harness, operation, harness_run, built_marketplace):
    """Only wiki targets receive the reminder; delivery does not require following it."""
    run = harness_run
    run.start("Create/update target and recover installed plugin advisory", live=True)
    run.report["artifact_version"] = (built_marketplace / "VERSION").read_text().strip()
    run.report["operation"] = operation
    subprocess.run(["git", "init", "-q", str(run.workspace)], check=True)
    subprocess.run(["git", "-C", str(run.workspace), "remote", "add", "origin",
                    "https://github.com/fixture/orientation-probe.git"], check=True)
    (run.workspace / ".gitignore").write_text(".llm-wiki/\n")
    seed_wiki(run.workspace, OrientationSeed.fresh())
    for case, expected in (("non_wiki", False), ("wiki", True)):
        parent = run.workspace / ".llm-wiki" if expected else run.workspace
        target = parent / f"{case}-{operation}-advisory.md"
        if operation == "update":
            target.write_text("before advisory probe\n")
        tool = "apply_patch" if harness == "codex" else "Write" if operation == "create" else "Edit"
        action = (f"Use {tool} to create {target} containing exactly {CONTENTS!r}." if operation == "create" else
                  f"Read {target}, then use {tool} to replace 'before advisory probe' with 'after advisory probe'.")
        prompt = (action + " This is a trivial test edit. Do not read other files, run verification, "
                  "update indexes/logs, or commit. Use only the requested write tool and, if needed, a read of the target. "
                  "After the tool completes, quote verbatim any post-write advisory supplied about wiki verification, "
                  "or reply NONE if none was supplied. Do not quote session-start guidance.")
        install_built_plugin(run, case, built_marketplace)
        output, transcript = run.session(case, prompt, trust_hooks=harness == "codex", writable=True)
        evidence = load_session_evidence(harness, run.root / case, transcript)
        run.record(case, advisory_evidence(evidence.transcript, evidence.context, output, target,
                                          expected=expected, evidence_source=evidence.source))
