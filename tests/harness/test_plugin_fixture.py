"""Changing a control's body preserves identity without leaking its marker."""

import json

import pytest

from .plugin_fixture import SkillFixture


@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_body_marker_only_appears_when_the_positive_control_is_written(tmp_path, harness):
    skill = SkillFixture.create(tmp_path, harness, "No body marker is supplied.")
    metadata = skill.metadata
    path = skill.directory / "SKILL.md"
    frontmatter = path.read_text().split("---", 2)[:2]
    assert skill.body_token not in json.dumps(metadata)
    assert all(skill.body_token not in file.read_text()
               for file in tmp_path.rglob("*") if file.is_file())

    skill.replace_body(f"Body-only marker: {skill.body_token}")
    assert skill.body_token in path.read_text()
    assert path.read_text().split("---", 2)[:2] == frontmatter
    assert skill.metadata == metadata

    skill.replace_body("No body marker is supplied.")
    assert skill.body_token not in path.read_text()
