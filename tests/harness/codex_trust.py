"""Exercise Codex hook approval through a private terminal and persisted home."""

import json
import re
import shlex
import subprocess
import time
import tomllib
from pathlib import Path

from .conversation import parse_codex
from .harness_support import REPO

# Codex rewords its dialogs between releases, so the terminal is read only for
# shape: numbered options under a cursor, or an input prompt. What each answer
# did is read back from the persisted config, never from the screen.
OPTION = re.compile(r"^\s*(›\s+)?\d+\.\s+(\S.*?)\s*$")
PROMPT = re.compile(r"^\s*›\s+\S")


def choices(text):
    """Options of a selection list whose cursor rests on its first entry."""
    found = [match for match in map(OPTION.match, text.splitlines()) if match]
    if not found or not found[0].group(1) or any(match.group(1) for match in found[1:]):
        return ()
    return tuple(match.group(2) for match in found)


def composer_ready(text):
    lines = text.splitlines()
    return not any(map(OPTION.match, lines)) and any(map(PROMPT.match, lines))


def persisted_config(probe):
    config = probe / "codex/config.toml"
    return tomllib.loads(config.read_text()) if config.exists() else {}


def hook_trust(probe):
    return {key: state["trusted_hash"]
            for key, state in persisted_config(probe).get("hooks", {}).get("state", {}).items()
            if state.get("trusted_hash")}


def workspace_trusted(probe, workspace):
    return any(state.get("trust_level") == "trusted" and Path(key).resolve() == workspace.resolve()
               for key, state in persisted_config(probe).get("projects", {}).items())


def approve_codex_hooks(run, probe):
    """Grant approval using the UI; never manufacture persisted trust state."""
    run.report["phase"] = "tui_approval"
    run.save()
    socket = run.root / "trust-tmux.sock"
    prefix = ["tmux", "-S", str(socket)]
    log = run.root / "trust-tui.txt"
    exited = run.root / "trust-tui.exit"
    env = run.env | {"ISOLATED_CODEX_ROOT": str(probe)}

    def tmux(*args, check=True):
        return subprocess.run([*prefix, *args], env=env, text=True, capture_output=True,
                              check=check, timeout=10)

    def screen():
        result = tmux("capture-pane", "-p", "-t", "trust", check=False)
        with log.open("a") as output:
            output.write(result.stdout + result.stderr + "\n")
        return result.stdout

    def wait_for(description, predicate):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            found = predicate()
            if found:
                return found
            if exited.exists():
                raise RuntimeError(f"Codex TUI exited before {description}; see {log}")
            time.sleep(0.2)
        raise RuntimeError(f"Timed out waiting for {description}; see {log}")

    args = [str(REPO / "scripts/isolated-codex.sh"), "--no-alt-screen", "-m", run.resolved_model]
    # The shell records wrapper completion, including its credential cleanup.
    command = shlex.join(args) + "; printf '%s' \"$?\" > " + shlex.quote(str(exited))
    try:
        tmux("-f", "/dev/null", "new-session", "-d", "-s", "trust", "-x", "120", "-y", "40",
             "-c", str(run.workspace), command)
        workspace_review = wait_for("workspace review", lambda: choices(screen()))
        tmux("send-keys", "-t", "trust", "Enter")
        wait_for("persisted workspace trust", lambda: workspace_trusted(probe, run.workspace))

        def hook_review():
            found = choices(screen())
            return len(found) > 1 and found != workspace_review

        wait_for("hook review", hook_review)
        # The second entry trusts every pending hook. A release that reorders
        # the list persists no approval, and the next wait fails with a capture.
        tmux("send-keys", "-t", "trust", "Down", "Enter")
        wait_for("persisted hook approval", lambda: hook_trust(probe))
        wait_for("ready composer", lambda: composer_ready(screen()))
        tmux("send-keys", "-t", "trust", "-l", "/exit")
        # Codex buffers rapid character bursts; submitting before rendering can
        # make Enter part of the paste instead of executing the slash command.
        wait_for("rendered exit command", lambda: "› /exit" in screen())
        tmux("send-keys", "-t", "trust", "Enter")
        wait_for("clean TUI exit", exited.exists)
        if exited.read_text() != "0":
            raise RuntimeError(f"Codex TUI failed; see {log}")
    finally:
        screen()
        tmux("kill-server", check=False)
        # Forced terminal shutdown can interrupt the wrapper's EXIT trap.
        (probe / "codex/auth.json").unlink(missing_ok=True)


def exec_with_persisted_home(run, probe, case, prompt):
    """Select only the transcript created by this fresh exec invocation."""
    directory = probe / "codex/sessions"
    before = set(directory.rglob("*.jsonl"))
    last = run.root / f"{case}.last-message"
    run.command(case, ["exec", "--skip-git-repo-check", "-s", "read-only", "-m", run.resolved_model,
                       "-o", str(last), prompt], probe)
    created = set(directory.rglob("*.jsonl")) - before
    if len(created) != 1:
        raise RuntimeError(f"Expected one new Codex transcript for {case}, got {len(created)}")
    transcript = created.pop()
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    return last.read_text(), parse_codex(records), transcript
