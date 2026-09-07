"""Instrumented resource fixture and deterministic first-execution classifier."""

import json
import os
from pathlib import Path
import secrets
import re
import shlex
import sys


def json_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def monitored_trace(calls, filename, attempts):
    """Only classify simple, observable interpreter launches; never guess."""
    commands = []
    for call in calls:
        if filename not in call.arguments:
            continue
        try:
            payload = json.loads(call.arguments)
        except json.JSONDecodeError:
            # Codex's code tool wraps exec_command in JavaScript. Accept a
            # literal cmd field only; computed commands need a richer auditor.
            fields = re.findall(r'\bcmd\s*:\s*("(?:[^"\\]|\\.)*")', call.arguments)
            if len(fields) != 1 or call.arguments.count(filename) != 1:
                return False
            command = json.loads(fields[0])
        else:
            if not isinstance(payload, dict):
                return False
            inputs = payload.get("input", payload.get("args", payload))
            if not isinstance(inputs, dict):
                return False
            command = inputs.get("command", inputs.get("cmd"))
        if not isinstance(command, str) or any(part in command for part in (";", "&&", "||", "$(", "`", "\n", ">", "<", "|")):
            return False
        try:
            argv = shlex.split(command)
        except ValueError:
            return False
        if len(argv) < 2 or argv[0] not in ("python", "python3") or filename not in argv[1]:
            return False
        commands.append(command)
    return len(commands) == len(attempts)


def make_resource_fixture(run):
    filename = "resource-probe-" + secrets.token_hex(8) + ".py"
    reference = "${CLAUDE_SKILL_DIR}" if run.harness == "claude" else "$SKILL_DIRECTORY"
    run.make_fixture(
        "Run the bundled probe to perform the requested operation:\n\n"
        f'```sh\npython3 "{reference}/scripts/{filename}" --probe {run.name}\n```\n'
        "Run it from the project working directory and report its output.\n"
    )
    scripts = run.plugin / "skills" / run.name / "scripts"
    scripts.mkdir()
    decoys = run.workspace / "scripts"
    decoys.mkdir()
    attempts = run.workspace / ".resource-attempts.jsonl"
    receipts = run.workspace / ".resource-receipts.jsonl"
    for directory, identity in ((scripts, "intended"), (decoys, "decoy")):
        (directory / filename).write_text(
            "import json, os, secrets, sys\nfrom pathlib import Path\n"
            "token = 'RESOURCE-' + secrets.token_hex(16)\n"
            f"receipt = {{'identity': {identity!r}, 'path': str(Path(__file__).resolve()), "
            "'argv': sys.argv[1:], 'cwd': os.getcwd(), 'attempt': os.environ.get('RESOURCE_ATTEMPT_ID'), 'token': token}\n"
            f"with open({str(receipts)!r}, 'a') as log:\n    log.write(json.dumps(receipt) + '\\n')\n"
            "print(token)\n"
        )
    # A receipt alone misses failed launches. Observe interpreter argv before
    # opening the script, retaining normal interpreter behavior and exit status.
    launchers = run.root / "launchers"
    launchers.mkdir()
    monitor = (
        f"#!{sys.executable}\nimport json, os, sys, uuid\n"
        f"if any({filename!r} in arg for arg in sys.argv[1:]):\n"
        "    attempt = uuid.uuid4().hex\n"
        "    os.environ['RESOURCE_ATTEMPT_ID'] = attempt\n"
        "    record = {'id': attempt, 'argv': sys.argv[1:], 'cwd': os.getcwd()}\n"
        f"    with open({str(attempts)!r}, 'a') as log:\n        log.write(json.dumps(record) + '\\n')\n"
        f"os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n"
    )
    for name in ("python", "python3"):
        path = launchers / name
        path.write_text(monitor)
        path.chmod(0o755)
    run.env["PATH"] = str(launchers) + os.pathsep + run.env["PATH"]
    return filename, attempts, receipts


def classify_resource_attempts(attempts, receipts, expected_script, workspace, expected_args):
    """Recovery is recorded, but can never turn a bad first launch into success."""
    expected_script = expected_script.resolve()
    workspace = workspace.resolve()
    if any(not isinstance(row, dict) for row in attempts + receipts):
        raise RuntimeError("malformed resource execution evidence")
    ids = [attempt.get("id") for attempt in attempts]
    if any(not isinstance(identifier, str) for identifier in ids) or len(set(ids)) != len(ids):
        raise RuntimeError("missing or duplicate launch IDs")
    if any(receipt.get("attempt") not in ids for receipt in receipts):
        return "infrastructure_failure"  # Execution bypassed the launch monitor.
    if not attempts:
        return "no_execution"
    successful = set()
    for attempt in attempts:
        argv = attempt.get("argv")
        cwd = attempt.get("cwd")
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
            raise RuntimeError("malformed launch argv")
        if not isinstance(cwd, str):
            raise RuntimeError("malformed launch cwd")
        script = (Path(cwd) / argv[0]).resolve()
        matching = [receipt for receipt in receipts if receipt.get("attempt") == attempt["id"]]
        if len(matching) != 1:
            continue
        receipt = matching[0]
        if (script == expected_script and argv[1:] == expected_args and Path(cwd).resolve() == workspace
                and receipt.get("identity") == "intended" and receipt.get("path") == str(expected_script)
                and receipt.get("argv") == expected_args and receipt.get("cwd") == str(workspace)):
            successful.add(attempt["id"])
    if attempts[0]["id"] in successful:
        return "first_attempt_success"
    return "recovered" if successful else "incorrect_execution"
