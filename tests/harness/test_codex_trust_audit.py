"""A shared Codex home must not lend old evidence to a new invocation."""

import json
from types import SimpleNamespace

import pytest

from .codex_trust import exec_with_persisted_home


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
