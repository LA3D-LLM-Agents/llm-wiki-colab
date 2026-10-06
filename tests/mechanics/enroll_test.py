"""Exercise built enrollment artifacts in disposable host/wiki repositories."""

import copy
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import validate

PLUGIN = Path(os.environ["PLUGIN_ROOT"])
HELPER = PLUGIN / "skills/wiki-enroll/scripts/enroll.py"
SCHEMA = json.loads(
    (PLUGIN / "skills/wiki-enroll/references/agent-card-1.0.schema.json").read_text()
)


def find_git() -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is not on PATH")
    return git


# Resolved once, before the tests put a wrapper named git first on PATH; the
# wrapper needs the real path to avoid calling itself.
GIT = find_git()


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "folder unlike repo"
        self.root.mkdir()
        self.git(self.root, "init", "-q")
        self.git(
            self.root,
            "remote",
            "add",
            "origin",
            "git@github.com:LA3D-LLM-Agents/example.git",
        )
        self.wiki = self.root / ".llm-wiki"
        self.wiki.mkdir()
        self.git(self.wiki, "init", "-q")
        self.git(
            self.wiki,
            "remote",
            "add",
            "origin",
            "https://github.com/LA3D-LLM-Agents/example.wiki.git",
        )
        (self.wiki / "Home_old-name.md").write_text("# Existing home\n")
        self.card = self.wiki / "Card_example.md"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.log = self.base / "gh-log"
        (self.bin / "gh").write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" >> "$GH_LOG"\nexit "${GH_EXIT:-0}"\n'
        )
        (self.bin / "gh").chmod(0o755)
        (self.bin / "git").write_text(
            '#!/bin/sh\nif [ "$1" = ls-remote ]; then exit 128; fi\n'
            f'exec {shlex.quote(GIT)} "$@"\n'
        )
        (self.bin / "git").chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            GH_LOG=str(self.log),
            GIT_TERMINAL_PROMPT="0",
        )
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)

    def git(self, cwd, *args):
        return subprocess.check_output(
            [GIT, "-C", str(cwd), *args], text=True
        ).strip()

    def invoke(self, *args, success=True, stdin="", helper=HELPER, env=None):
        result = subprocess.run(
            [sys.executable, str(helper), *args],
            cwd=self.root,
            env=env or self.env,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def create(self, *args):
        return self.invoke(
            "--non-interactive",
            "--description",
            'Explain: "evidence" — safe',
            "--capability",
            "Read: methods",
            *args,
        )

    def parsed(self):
        return yaml.safe_load(self.card.read_text().split("---\n", 2)[1])

    def test_remote_identity_canonical_filename_safe_yaml_and_no_github_calls(self):
        out = self.create("--topic", "methods")
        card = self.parsed()
        self.assertEqual(card["id"], "LA3D-LLM-Agents/example")
        self.assertEqual(card["up"], "[[Home_old-name]]")
        self.assertEqual(card["capabilities"], ["Read: methods"])
        self.assertEqual(card["description"], 'Explain: "evidence" — safe')
        validate(card["x-fabric-card"], SCHEMA)
        self.assertEqual(
            card["x-fabric-card"]["interfaces"][0]["kind"], "clone-and-invoke"
        )
        self.assertFalse(self.log.exists())
        self.assertIn("commit --only", out.stdout)
        self.assertIn("Index inclusion: not verified", out.stdout)
        self.assertEqual(self.git(self.wiki, "diff", "--cached", "--name-only"), "")

    def test_dry_run_and_explicit_topic_target(self):
        result = self.create("--dry-run", "--add-topic")
        self.assertFalse(self.card.exists())
        self.assertFalse(self.log.exists())
        self.assertIn(
            "gh repo edit LA3D-LLM-Agents/example --add-topic nd-llm-wiki",
            result.stderr,
        )
        self.create("--add-topic")
        self.assertEqual(
            self.log.read_text().splitlines(),
            ["repo", "edit", "LA3D-LLM-Agents/example", "--add-topic", "nd-llm-wiki"],
        )

    def test_noninteractive_missing_fields_and_interactive_eof(self):
        self.invoke("--non-interactive", success=False)
        self.invoke(
            "--non-interactive", "--description", "Only description", success=False
        )
        result = self.invoke(success=False)
        self.assertIn("Input ended", result.stderr)
        self.assertFalse(self.card.exists())

    def test_eof_and_declined_confirmation_never_add_topic(self):
        for stdin in ("", "n\n"):
            result = self.invoke(
                "--description",
                "D",
                "--capability",
                "C",
                "--topic",
                "T",
                "--add-topic",
                stdin=stdin,
                success=bool(stdin),
            )
            self.assertFalse(self.card.exists(), result.stdout)
            self.assertFalse(self.log.exists())

    def test_alternate_wiki_and_explicit_repo_override(self):
        alternative = self.root / "memory elsewhere"
        self.wiki.rename(alternative)
        self.git(
            self.root,
            "remote",
            "set-url",
            "origin",
            "git@github-alias:team/example.git",
        )
        self.create("--repo", "LA3D-LLM-Agents/example", "--wiki-dir", str(alternative))
        self.assertTrue((alternative / "Card_example.md").exists())

    def test_wrong_wiki_attachment_refused(self):
        self.git(
            self.wiki,
            "remote",
            "set-url",
            "origin",
            "https://github.com/other/repo.wiki.git",
        )
        result = self.invoke("--non-interactive", success=False)
        self.assertIn("does not match", result.stderr)
        self.assertFalse(self.card.exists())

    def test_local_draft_does_not_advertise_unconfigured_route(self):
        self.git(self.wiki, "remote", "remove", "origin")
        result = self.create()
        self.assertEqual(self.parsed()["x-fabric-card"]["interfaces"], [])
        self.assertEqual(self.parsed()["x-fabric-card"]["knowledge_bundles"], [])
        self.assertIn("local draft only", result.stdout)
        self.invoke("--add-topic", success=False)
        self.assertFalse(self.log.exists())

    def test_remote_check_failure_does_not_write_or_claim_missing_wiki(self):
        result = self.invoke("--check-remote", "--non-interactive", success=False)
        self.assertIn("Command failed: git ls-remote", result.stderr)
        self.assertFalse(self.card.exists())

    def test_legacy_update_preserves_identity_custom_fields_and_exact_body(self):
        body = b"\r\n# Custom prose\r\nDo not lose this.\r\n"
        self.card.write_bytes(
            b"---\nid: historic/stable-agent\ndescription: Old\ncapabilities: [Explain]\ncustom: {keep: true}\nx-llm-wiki:\n  topics: [old]\n  endpoints: {ask: custom}\n---\n"
            + body
        )
        self.invoke("--non-interactive", "--update", "--description", "New: scope")
        card = self.parsed()
        self.assertEqual(card["id"], "historic/stable-agent")
        self.assertEqual(card["custom"], {"keep": True})
        self.assertEqual(card["x-llm-wiki"]["endpoints"], {"ask": "custom"})
        self.assertEqual(card["x-llm-wiki"]["topics"], ["old"])
        self.assertTrue(self.card.read_bytes().endswith(body))
        validate(card["x-fabric-card"], SCHEMA)

    def test_existing_without_update_is_idempotent(self):
        self.create()
        original = self.card.read_bytes()
        stamp = self.card.stat().st_mtime_ns
        self.invoke("--non-interactive")
        self.assertEqual(self.card.read_bytes(), original)
        self.assertEqual(self.card.stat().st_mtime_ns, stamp)
        self.invoke("--non-interactive", "--description", "Changed", success=False)

    def test_structured_update_preserves_ids_body_and_is_idempotent(self):
        self.create()
        before = self.parsed()["x-fabric-card"]
        skills = copy.deepcopy(before["skills"])
        skills[0]["name"] = "Renamed"
        skills[0]["description"] = "Different: description"
        path = self.base / "skills.json"
        path.write_text(json.dumps(skills))
        self.invoke("--non-interactive", "--update", "--skills-json", str(path))
        after = self.parsed()
        self.assertEqual(
            after["x-fabric-card"]["skills"][0]["id"], before["skills"][0]["id"]
        )
        self.assertEqual(after["capabilities"], ["Different: description"])
        stamp = self.card.stat().st_mtime_ns
        self.invoke("--non-interactive", "--update")
        self.assertEqual(self.card.stat().st_mtime_ns, stamp)

    def test_invalid_updates_leave_bytes_unchanged(self):
        self.create()
        before = self.card.read_bytes()
        for mutate in (
            "version",
            "id",
            "card_url",
            "skill_id",
            "duplicate_skill",
            "bundle_reference",
        ):
            card = copy.deepcopy(self.parsed()["x-fabric-card"])
            if mutate == "version":
                card["schema_version"] = "99"
            elif mutate == "id":
                card["id"] = "renamed/agent"
            elif mutate == "card_url":
                card["card_url"] = "https://example.org/card"
            elif mutate == "skill_id":
                card["skills"][0]["id"] = "renamed"
            elif mutate == "duplicate_skill":
                card["skills"].append(copy.deepcopy(card["skills"][0]))
            elif mutate == "bundle_reference":
                card["interfaces"][0]["bundle_id"] = "absent"
            path = self.base / "card.json"
            path.write_text(json.dumps(card))
            with self.subTest(mutate=mutate):
                self.invoke(
                    "--non-interactive",
                    "--update",
                    "--card-json",
                    str(path),
                    success=False,
                )
                self.assertEqual(self.card.read_bytes(), before)

    def test_duplicate_yaml_and_conflicting_dual_fields_are_rejected(self):
        for content in (
            "---\nid: a/b\nid: c/d\n---\n",
            "---\ncapabilities:\n- Read: data\n---\n",
        ):
            self.card.write_text(content)
            self.invoke("--update", "--non-interactive", success=False)
            self.assertEqual(self.card.read_text(), content)
        self.card.unlink()
        self.create()
        parsed = self.parsed()
        parsed["description"] = "Conflict"
        self.card.write_text("---\n" + yaml.safe_dump(parsed) + "---\nBody")
        before = self.card.read_bytes()
        self.invoke("--update", "--non-interactive", success=False)
        self.assertEqual(self.card.read_bytes(), before)

    def test_other_card_filename_and_symlink_refused(self):
        (self.wiki / "Card_historical.md").write_text("Existing")
        self.invoke("--non-interactive", success=False)
        (self.wiki / "Card_historical.md").unlink()
        target = self.base / "outside"
        target.write_text("original")
        self.card.symlink_to(target)
        self.invoke("--non-interactive", success=False)
        self.assertEqual(target.read_text(), "original")

    def test_topic_failure_reports_local_card_status(self):
        result = self.invoke(
            "--non-interactive",
            "--description",
            "D",
            "--capability",
            "C",
            "--add-topic",
            env=dict(self.env, GH_EXIT="1"),
            success=False,
        )
        self.assertTrue(self.card.exists())
        self.assertIn("topic registration failed", result.stderr)

    def test_built_adapters_are_equivalent_and_independent_of_harness_env(self):
        for variable in ("CODEX_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT"):
            other = Path(os.environ[variable]) / "skills/wiki-enroll/scripts/enroll.py"
            self.assertEqual(other.read_bytes(), HELPER.read_bytes())
            self.invoke(
                "--non-interactive",
                "--dry-run",
                "--description",
                "D",
                "--capability",
                "C",
                helper=other,
            )

    def test_printed_commands_commit_only_card(self):
        import shlex

        self.git(self.wiki, "config", "user.name", "Enrollment Test")
        self.git(self.wiki, "config", "user.email", "test@example.org")
        self.git(self.wiki, "config", "commit.gpgsign", "false")
        unrelated = self.wiki / "unrelated.md"
        unrelated.write_text("Other work")
        self.git(self.wiki, "add", "unrelated.md")
        result = self.create()
        commands = [
            shlex.split(line.strip())
            for line in result.stdout.splitlines()
            if line.startswith("  git")
        ]
        for command in commands[:2]:
            subprocess.run(command, env=self.env, check=True, capture_output=True)
        self.assertEqual(
            self.git(self.wiki, "diff", "--cached", "--name-only"), "unrelated.md"
        )
        self.assertEqual(
            self.git(self.wiki, "ls-tree", "--name-only", "HEAD"), "Card_example.md"
        )

    def test_concurrent_change_does_not_get_overwritten(self):
        import runpy

        module = runpy.run_path(str(HELPER))
        self.card.write_bytes(b"new concurrent contents")
        with self.assertRaises(module["EnrollError"]):
            module["write_atomic"](self.card, b"candidate", b"old snapshot")
        self.assertEqual(self.card.read_bytes(), b"new concurrent contents")
        self.assertEqual(list(self.wiki.glob(".enroll-*")), [])

    def test_importer_limits_rejected_before_writing(self):
        self.invoke(
            "--non-interactive",
            "--description",
            "D" * 4001,
            "--capability",
            "C",
            success=False,
        )
        self.assertFalse(self.card.exists())

    def test_multiline_description_yaml_roundtrip(self):
        self.invoke(
            "--non-interactive",
            "--description",
            '---\nquoted: "text"\nUnicode — next',
            "--capability",
            "Explain",
        )
        # Read using the helper's complete delimiter convention, not a raw substring split.
        import re

        content = re.match(r"---\n(.*?)\n---\n", self.card.read_text(), re.S).group(1)
        self.assertEqual(
            yaml.safe_load(content)["description"],
            '---\nquoted: "text"\nUnicode — next',
        )


if __name__ == "__main__":
    unittest.main()
