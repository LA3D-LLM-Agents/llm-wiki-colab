"""Shared-home evidence selection and wording-independent terminal reading."""

import json
from types import SimpleNamespace

import pytest

from .codex_trust import choices, composer_ready, exec_with_persisted_home, workspace_trusted

# Terminal captures from codex-cli 0.156.1, blank lines removed.
FOLDER_DIALOG = """\
  Folder access
  /tmp/codex-tui-probe-emrujhl4/workspace
  Trust this folder? Codex can read, edit, and run files here, subject to your permission settings. Folder settings
  can run code automatically, even without a model request. Continue only if you trust these files. Your trust
  decision will be saved.
› 1. Trust and continue
  2. Quit
  enter continue · esc quit
"""
HOOK_DIALOG = """\
  Hooks need review
  1 hook is new or changed.
  Hooks can run outside the sandbox after you trust them.
› 1. Review hooks
  2. Trust all and continue
  3. Continue without trusting (hooks won't run)
  enter confirm · esc skip
"""
COMPOSER = """\
╭────────────────────────────────────────────────────╮
│ >_ OpenAI Codex (v0.156.1)                         │
│                                                    │
│ model:     GPT-5.6-Luna   /model to change         │
│ directory: /tmp/codex-tui-probe-emrujhl4/workspace │
╰────────────────────────────────────────────────────╯
  Tip: New Use /fast to enable our fastest inference with increased plan usage.
› Ask Codex to do anything
  GPT-5.6-Luna default · /tmp/codex-tui-probe-emrujhl4/workspace
"""


@pytest.mark.parametrize("created", [0, 1, 2])
def test_shared_home_selects_exactly_one_new_transcript(tmp_path, created):
    directory = tmp_path / "shared/codex/sessions"
    directory.mkdir(parents=True)

    def record(text):
        return json.dumps({"type": "response_item", "payload": {
            "type": "message", "role": "developer", "content": text}})

    (directory / "prior-tui.jsonl").write_text(record("OLD-TUI-TOKEN"))

    def command(label, args, probe):
        (tmp_path / f"{label}.last-message").write_text("NEW-EXEC-TOKEN")
        for index in range(created):
            (directory / f"exec-{index}.jsonl").write_text(record("NEW-EXEC-TOKEN"))

    run = SimpleNamespace(root=tmp_path, resolved_model="fixture-model", command=command)
    if created != 1:
        with pytest.raises(RuntimeError, match="Expected one new Codex transcript"):
            exec_with_persisted_home(run, tmp_path / "shared", "exec", "fixture prompt")
    else:
        output, conversation, transcript = exec_with_persisted_home(
            run, tmp_path / "shared", "exec", "fixture prompt")
        assert output == "NEW-EXEC-TOKEN"
        assert conversation.incoming == [("developer", "NEW-EXEC-TOKEN")]
        assert transcript == directory / "exec-0.jsonl"


@pytest.mark.parametrize("screen,expected", [
    pytest.param(FOLDER_DIALOG, ("Trust and continue", "Quit"), id="folder"),
    pytest.param(HOOK_DIALOG, ("Review hooks", "Trust all and continue",
                               "Continue without trusting (hooks won't run)"), id="hooks"),
    pytest.param(COMPOSER, (), id="composer"),
    pytest.param("", (), id="blank"),
])
def test_selection_list_is_read_from_its_shape(screen, expected):
    assert choices(screen) == expected


def test_reworded_dialog_reads_the_same():
    reworded = FOLDER_DIALOG.replace("Folder access", "Workspace").replace(
        "Trust this folder?", "Do you trust the contents of this directory?")
    assert reworded != FOLDER_DIALOG
    assert choices(reworded) == ("Trust and continue", "Quit")


def test_list_with_the_cursor_off_its_first_option_is_not_ready():
    moved = HOOK_DIALOG.replace("› 1. Review hooks", "  1. Review hooks").replace(
        "  2. Trust all", "› 2. Trust all")
    assert choices(moved) == ()


@pytest.mark.parametrize("screen,ready", [
    pytest.param(COMPOSER, True, id="composer"), pytest.param(FOLDER_DIALOG, False, id="folder"),
    pytest.param(HOOK_DIALOG, False, id="hooks"), pytest.param("", False, id="blank")])
def test_composer_is_ready_only_once_dialogs_are_gone(screen, ready):
    assert composer_ready(screen) is ready


@pytest.mark.parametrize("level,named,trusted", [
    ("trusted", "workspace", True), ("untrusted", "workspace", False), ("trusted", "elsewhere", False)])
def test_workspace_trust_is_read_from_the_persisted_project_entry(tmp_path, level, named, trusted):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    probe = tmp_path / "shared"
    assert workspace_trusted(probe, workspace) is False
    (probe / "codex").mkdir(parents=True)
    (probe / "codex/config.toml").write_text(
        f'[tui]\nscreen_reader_detection_done = true\n\n[projects."{tmp_path / named}"]\ntrust_level = "{level}"\n')
    assert workspace_trusted(probe, workspace) is trusted
