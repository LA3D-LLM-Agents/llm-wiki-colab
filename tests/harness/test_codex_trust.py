"""Interactive hook approval survives fresh headless processes."""

import json
import shutil

import pytest

from .codex_trust import approve_codex_hooks, exec_with_persisted_home, hook_trust
from .harness_support import write_json
from .plugin_install import install_fixture
from .session_context import TOKEN, make_session_fixture, session_evidence
from .skill_assertions import audit_messages

PROMPT = "What is the session-start token? Reply with exactly the token, or NONE if none was supplied. Do not use tools."


@pytest.mark.capability
@pytest.mark.live
@pytest.mark.parametrize("harness", ["codex"])
def test_codex_hook_trust_persists_from_tui_to_exec(harness, harness_run):
    """Untrusted hooks stay silent; UI approval enables successive fresh execs."""
    if not shutil.which("tmux"):
        pytest.skip("tmux is required for interactive hook approval")
    run = harness_run
    run.start(PROMPT, live=True)
    probe = run.root / "shared"
    plugin, capture = make_session_fixture(run, "shared", emit=True)
    install_fixture(run, "shared", plugin)
    assert not hook_trust(probe), "installation unexpectedly granted hook trust"

    output, conversation, _ = exec_with_persisted_home(run, probe, "before_approval", PROMPT)
    audit_messages(conversation)
    assert output.strip(), "empty model response"
    assert not capture.exists(), "untrusted hook executed"
    assert not TOKEN.search(output)
    assert not any(TOKEN.search(text) for _, text in conversation.incoming)
    assert not hook_trust(probe), "headless execution unexpectedly granted hook trust"
    run.record("before_approval", {"hook_executed": False, "context_received": False})

    approve_codex_hooks(run, probe)
    trusted = hook_trust(probe)
    assert len(trusted) == 1, "expected trust for exactly the fixture hook"
    assert not (probe / "codex/auth.json").exists(), "TUI wrapper did not clean up credentials"
    run.record("tui_approval", {"trusted_hooks": trusted, "exited": True})

    tokens = set()
    if capture.exists():
        tokens.add(json.loads(capture.read_text())["token"])
    for case in ("after_approval", "repeat_exec"):
        # Remove any TUI/prior receipt without changing the trusted hook definition.
        capture.unlink(missing_ok=True)
        output, conversation, transcript = exec_with_persisted_home(run, probe, case, PROMPT)
        assert capture.is_file(), "persisted approval did not enable the hook"
        captured = json.loads(capture.read_text())
        write_json(run.root / f"{case}.hook.json", captured)
        assert captured["payload"]["transcript_path"] == str(transcript)
        assert captured["payload"]["hook_event_name"] == "SessionStart"
        assert captured["token"] not in tokens, "prior session token reused"
        tokens.add(captured["token"])
        evidence = session_evidence(conversation, output, captured, emitted=True)
        assert hook_trust(probe) == trusted, "exec changed the persisted approval"
        run.record(case, evidence | {"hook_trust": "persisted", "transcript": str(transcript)})
