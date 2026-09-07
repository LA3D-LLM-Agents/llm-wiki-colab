"""Isolated CLI execution, session lifecycle, and evidence reporting."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from .conversation import load_conversation
from .harness_session import session_claude, session_codex, session_cursor

REPO = Path(__file__).resolve().parents[2]

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


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
        self.report["prompt"] = prompt
        self.report["version"] = self.command("version", ["--version"], self.root / "version-probe").strip()
        self.save()

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
        write_json(self.root / "results.json", self.report)
