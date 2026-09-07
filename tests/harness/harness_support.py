"""Execution and fixture construction for isolated capability probes."""

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import uuid

from .conversation import load_conversation
from .plugin_install import install_codex
from .harness_session import session_claude, session_codex, session_cursor

REPO = Path(__file__).resolve().parents[2]

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def plugin_fixture(root, harness):
    market = root / "fixture"
    plugin = market / "metadata-fixture"
    write_json(plugin / f".{harness}-plugin/plugin.json", {
        "name": "metadata-fixture", "version": "0.0.1",
        "description": "Skill metadata capability fixture.",
    })
    if harness == "codex":
        write_json(market / ".agents/plugins/marketplace.json", {
            "name": "metadata-market", "plugins": [{
                "name": "metadata-fixture",
                "source": {"source": "local", "path": "./metadata-fixture"},
                "description": "Skill metadata capability fixture.",
            }],
        })
    return market, plugin


def fixture(root, harness, name, description, body_text):
    market, plugin = plugin_fixture(root, harness)
    skill = plugin / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: {name}\ndescription: {description}\n---\n"
                     f"{body_text}\n")
    return market, plugin


def credentials(harness):
    binary = "cursor-agent" if harness == "cursor" else harness
    default = {"claude": ".claude/.credentials.json", "codex": ".codex/auth.json",
               "cursor": ".config/cursor/auth.json"}[harness]
    auth = Path(os.environ.get(f"ISOLATED_{harness.upper()}_AUTH", Path.home() / default))
    if not shutil.which(binary):
        return None, f"{binary} missing from PATH"
    if not auth.is_file():
        return None, f"{harness} wrapper credentials missing"
    return auth.resolve(), None


class HarnessRun:
    """One capability pair with independent harness state for each case."""

    def __init__(self, root, harness, auth, model):
        self.root, self.harness, self.model = root, harness, model
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.env = os.environ.copy()
        self.env.pop("ISOLATED_CURSOR_ALLOW_ACCOUNT_PLUGINS", None)
        self.env.pop("ISOLATED_CLAUDE_ENV", None)
        self.env[f"ISOLATED_{harness.upper()}_AUTH"] = str(auth)
        self.name = "metadata-probe-" + secrets.token_hex(8)
        self.description_token = "DESCRIPTION-" + secrets.token_hex(16)
        self.body_token = "BODY-" + secrets.token_hex(16)
        self.description = f"Inert capability fixture. Description marker {self.description_token}."
        self.report = {"harness": harness, "model": self.resolved_model, "cases": {}}

    @property
    def resolved_model(self):
        return self.model or {"claude": "haiku", "codex": "gpt-5.6-luna",
                              "cursor": "harness default"}[self.harness]

    def command(self, label, args, probe):
        self.report["phase"] = label
        self.save()
        env = self.env | {f"ISOLATED_{self.harness.upper()}_ROOT": str(probe)}
        wrapper = REPO / "scripts" / f"isolated-{self.harness}.sh"
        with (self.root / f"{label}.stdout").open("w") as out, (self.root / f"{label}.stderr").open("w") as err:
            result = subprocess.run([str(wrapper), *args], cwd=self.workspace, env=env,
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        if result.returncode:
            raise RuntimeError(f"{label} exited {result.returncode}; see {label}.stderr")
        return (self.root / f"{label}.stdout").read_text()

    def start(self, prompt, *, live):
        if not live:
            self.report["model"] = None
        self.report.update({"prompt": prompt, "name": self.name, "description": self.description,
                            "loading": "local marketplace install" if self.harness == "codex" else "--plugin-dir"})
        self.report["version"] = self.command("version", ["--version"], self.root / "version-probe").strip()
        self.save()

    def make_fixture(self, body_text):
        self.market, self.plugin = fixture(self.root, self.harness, self.name, self.description, body_text)

    def replace_body(self, body_text):
        skill = self.plugin / "skills" / self.name / "SKILL.md"
        skill.write_text(f"---\nname: {self.name}\ndescription: {self.description}\n---\n{body_text}\n")

    def install_fixture(self, case):
        """Prepare the fixture and return any required session directory override."""
        if self.harness == "codex":
            install_codex(self, case, self.market, self.plugin, "metadata-market")
            return None
        return self.plugin

    def session(self, case, prompt, *, plugin_dir=None, trust_hooks=False, writable=False):
        self.report["writable"] = writable
        self.report["hook_trust"] = "bypassed" if trust_hooks else "default"
        probe = self.root / case
        session_id = str(uuid.uuid4())
        execute = {"claude": session_claude, "codex": session_codex, "cursor": session_cursor}[self.harness]
        output = execute(self, case, prompt, session_id, plugin_dir=plugin_dir,
                         trust_hooks=trust_hooks, writable=writable)
        return output, load_conversation(self.harness, probe, session_id)

    def record(self, case, evidence):
        self.report["phase"] = case
        self.report["cases"][case] = evidence
        self.save()

    def save(self):
        # The body token must not be exposed in pre-session metadata.
        write_json(self.root / "results.json", self.report)

