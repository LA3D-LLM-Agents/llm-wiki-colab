"""Resolve and validate opt-in before maintenance or orientation."""
from pathlib import Path
import shutil
import subprocess


def run(state):
    root = state["project_root"]
    found = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                           capture_output=True, text=True)
    if found.returncode == 0:
        root = Path(found.stdout.strip())
    state["project_root"] = root
    wiki = root / ".llm-wiki"
    state["wiki_dir"] = wiki
    if not wiki.exists():
        state["stop"] = True
        return
    top = subprocess.run(["git", "-C", str(wiki), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode or Path(top.stdout.strip()).resolve() != wiki.resolve():
        state["warnings"].append(
            "llm-wiki: .llm-wiki/ is not a separate Git checkout. "
            "Repair the attachment before editing or committing wiki files.")
        state["stop"] = True
        return
    if not shutil.which("jq"):
        state["warnings"].append(
            "llm-wiki: jq not found on PATH; automatic verification reminders "
            "after wiki edits are unavailable. Make jq available to the hook "
            "environment to restore them.")
