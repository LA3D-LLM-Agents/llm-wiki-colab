"""Exercise Codex hook approval through a private terminal and persisted home."""

import json
import shlex
import subprocess
import time
import tomllib

from .conversation import parse_codex
from .harness_support import REPO


def hook_trust(probe):
    config = probe / "codex/config.toml"
    if not config.exists():
        return {}
    return {key: state["trusted_hash"]
            for key, state in tomllib.loads(config.read_text()).get("hooks", {}).get("state", {}).items()
            if state.get("trusted_hash")}


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
            if predicate():
                return
            if exited.exists():
                raise RuntimeError(f"Codex TUI exited before {description}; see {log}")
            time.sleep(0.2)
        raise RuntimeError(f"Timed out waiting for {description}; see {log}")

    def hook_review_visible():
        text = screen()
        return all(part in text for part in (
            "Hooks need review", "1 hook is new or changed.", "Trust all and continue"))

    args = [str(REPO / "scripts/isolated-codex.sh"), "--no-alt-screen", "-m", run.resolved_model]
    # The shell records wrapper completion, including its credential cleanup.
    command = shlex.join(args) + "; printf '%s' \"$?\" > " + shlex.quote(str(exited))
    try:
        tmux("-f", "/dev/null", "new-session", "-d", "-s", "trust", "-x", "120", "-y", "40",
             "-c", str(run.workspace), command)
        wait_for("workspace review", lambda: "Do you trust the contents of this directory?" in screen())
        tmux("send-keys", "-t", "trust", "Enter")
        wait_for("single fixture hook review", hook_review_visible)
        tmux("send-keys", "-t", "trust", "Down", "Enter")
        wait_for("persisted hook approval", lambda: bool(hook_trust(probe)))
        wait_for("ready composer", lambda: "Ask Codex to do anything" in screen())
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
