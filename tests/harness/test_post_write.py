"""Post-write advisory delivery, independent of whether the advice is followed."""

import json

import pytest

from .conversation import load_claude_request
from .post_write import make_post_write_fixture, post_write_evidence


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.parametrize("harness,tool", [("claude", "Write"), ("claude", "Edit"),
                                         ("codex", "apply_patch"), ("cursor", "Write")])
def test_post_write_advisory(harness, tool, harness_run):
    """Suppressing hook output removes the advisory while the write still succeeds."""
    run = harness_run
    run.start("Explicit target write followed by advisory token recovery", live=True)
    for case, emit in (("advisory_absent", False), ("advisory_present", True)):
        target = run.workspace / f"{case}.md"
        if tool == "Edit":
            target.write_text("before probe\n")
            action = f"Read {target}, then use Edit to replace 'before probe' with 'after probe'."
        else:
            action = f"Use {tool} to create {target} containing exactly 'after probe' followed by a newline."
        prompt = (action + " Then report the post-write advisory token exactly, or NONE if none was supplied. "
                  "Use only the requested write tool and, if required, a read of this target file. Do not read other files.")
        capture = make_post_write_fixture(run, case, tool, target, emit=emit)
        plugin_dir = run.install_fixture(case)
        output, conversation = run.session(case, prompt, plugin_dir=plugin_dir,
                                            trust_hooks=harness == "codex", writable=True)
        assert capture.is_file(), "post-write hook did not execute"
        captures = [json.loads(line) for line in capture.read_text().splitlines()]
        request = load_claude_request(run.root / case) if harness == "claude" else None
        run.record(case, post_write_evidence(conversation, output, captures, tool, target,
                                             emitted=emit, request_context=request))
