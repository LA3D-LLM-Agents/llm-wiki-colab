#!/usr/bin/env python3
"""Explicit capability probe; Claude/Cursor spend two model calls per harness."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import uuid


REPO = Path(__file__).resolve().parents[2]
PROMPT = (
    "Report the names and complete descriptions of available skills whose names "
    "start with metadata-probe-. Use only the skill metadata already in your "
    "context. Do not invoke skills or use any tools, including file reads. "
    "If none are available, reply NONE."
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root, harness, name, description, body_token):
    market = root / "fixture"
    plugin = market / "metadata-fixture"
    write_json(plugin / f".{harness}-plugin/plugin.json", {
        "name": "metadata-fixture", "version": "0.0.1",
        "description": "Skill metadata capability fixture.",
    })
    skill = plugin / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: {name}\ndescription: {description}\n---\n"
                     f"Body-only marker: {body_token}\n")
    if harness == "codex":
        write_json(market / ".agents/plugins/marketplace.json", {
            "name": "metadata-market", "plugins": [{
                "name": "metadata-fixture",
                "source": {"source": "local", "path": "./metadata-fixture"},
                "description": "Skill metadata capability fixture.",
            }],
        })
    return market, plugin


def audit_messages(messages):
    """Fail closed on absent assistant evidence or any recorded tool activity."""
    assistant_seen = False
    for msg in messages:
        role = msg.get("role", msg.get("type"))
        if role == "tool":
            raise RuntimeError("tool message in conversation; metadata-only proof invalid")
        content = msg.get("content", msg.get("message", {}).get("content", []))
        if isinstance(content, str) and content.startswith("["):
            content = json.loads(content)
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    raise RuntimeError("unrecognized conversation part")
                kind = part.get("type", "")
                if kind.startswith("tool") or kind in ("function_call", "function_call_output"):
                    raise RuntimeError(f"recorded {kind}; metadata-only proof invalid")
                assistant_seen |= role == "assistant" and kind == "text" and bool(part.get("text"))
        elif role == "assistant" and isinstance(content, str) and content:
            assistant_seen = True
    if not assistant_seen:
        raise RuntimeError("no assistant messages available for tool-use audit")


def rendered_prompt(raw):
    messages = json.loads(raw)
    if not isinstance(messages, list) or not messages:
        raise RuntimeError("expected a nonempty rendered message list")
    texts = []
    for message in messages:
        if not isinstance(message, dict) or message.get("type") != "message":
            raise RuntimeError("unrecognized rendered prompt message")
        if message.get("role") not in ("system", "developer", "user"):
            raise RuntimeError("unexpected role in pre-session prompt")
        content = message.get("content")
        if not isinstance(content, list):
            raise RuntimeError("unrecognized rendered prompt content")
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "input_text":
                raise RuntimeError("unrecognized rendered prompt part")
            if not isinstance(part.get("text"), str):
                raise RuntimeError("rendered prompt text missing or malformed")
            texts.append(part["text"])
    if not any(texts):
        raise RuntimeError("empty rendered prompt")
    return "\n".join(texts)


def check_metadata(output, name, token, body, installed):
    if not output.strip():
        raise RuntimeError("empty evidence")
    if body in output:
        raise RuntimeError("skill body appeared; metadata-only boundary not established")
    if installed:
        if name not in output or token not in output:
            raise RuntimeError("name or description marker missing")
    elif name in output or token in output:
        raise RuntimeError("fixture metadata appeared without plugin loaded")


def audit(harness, probe, session):
    if harness == "claude":
        files = list((probe / "claude/projects").rglob(f"{session}.jsonl"))
        if len(files) != 1:
            raise RuntimeError("expected exactly one Claude session transcript")
        audit_messages([json.loads(line) for line in files[0].read_text().splitlines()])
    else:
        files = list((probe / "config/chats").rglob("store.db"))
        if len(files) != 1:
            raise RuntimeError("expected exactly one Cursor chat store")
        with sqlite3.connect(f"file:{files[0]}?mode=ro", uri=True) as db:
            messages = []
            for (data,) in db.execute("SELECT data FROM blobs"):
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                if data.startswith("{"):
                    msg = json.loads(data)
                    if "role" in msg:
                        messages.append(msg)
        audit_messages(messages)


def run_harness(harness, root, model, body_probe=False):
    binary = "cursor-agent" if harness == "cursor" else harness
    auth_default = {"claude": ".claude/.credentials.json", "codex": ".codex/auth.json",
                    "cursor": ".config/cursor/auth.json"}[harness]
    auth = Path(os.environ.get(f"ISOLATED_{harness.upper()}_AUTH", Path.home() / auth_default))
    if not shutil.which(binary) or not auth.is_file():
        return {"status": "skip", "reason": "CLI or wrapper credentials missing"}
    root.mkdir()
    workspace = root / "workspace"
    workspace.mkdir()
    name = "metadata-probe-" + secrets.token_hex(8)
    token = "DESCRIPTION-" + secrets.token_hex(16)
    body = "BODY-" + secrets.token_hex(16)
    description = f"Inert capability fixture. Description marker {token}."
    market, plugin = fixture(root, harness, name, description, body)
    skill_file = plugin / "skills" / name / "SKILL.md"
    full_skill = skill_file.read_text()
    if body_probe:
        # Both cases install the same skill. Only its body changes, and the
        # positive token does not exist on disk until the control has finished.
        skill_file.write_text(full_skill.replace(f"Body-only marker: {body}", "No body marker is supplied."))
    prompt = (f"Load the skill {name}. "
              "Report its Body-only marker exactly, or NONE if it has no such marker.") if body_probe else PROMPT
    env = os.environ.copy()
    # Do not inherit opt-outs or extra settings that weaken isolation.
    env.pop("ISOLATED_CURSOR_ALLOW_ACCOUNT_PLUGINS", None)
    env.pop("ISOLATED_CLAUDE_ENV", None)
    env[f"ISOLATED_{harness.upper()}_AUTH"] = str(auth.resolve())
    wrapper = REPO / "scripts" / f"isolated-{harness}.sh"

    def command(label, args, probe):
        env[f"ISOLATED_{harness.upper()}_ROOT"] = str(probe)
        with (root / f"{label}.stdout").open("w") as out, (root / f"{label}.stderr").open("w") as err:
            result = subprocess.run([str(wrapper), *args], cwd=workspace, env=env,
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        if result.returncode:
            raise RuntimeError(f"{label} exited {result.returncode}; see {label}.stderr")
        return (root / f"{label}.stdout").read_text()

    version = command("version", ["--version"], root / "version-probe").strip()
    write_json(root / "run.json", {
        "harness": harness, "version": version, "model_override": model,
        "name": name, "description": description,
        "prompt": prompt if body_probe or harness != "codex" else None,
        "loading": "local marketplace install" if harness == "codex" else "--plugin-dir",
    })
    for installed in (False, True):
        phase = "present" if installed else "absent"
        if body_probe and installed:
            skill_file.write_text(full_skill)
        print(f"{harness}: {phase} control", flush=True)
        probe = root / phase
        session = str(uuid.uuid4())
        if harness == "codex":
            if installed or body_probe:
                command(f"{phase}-marketplace", ["plugin", "marketplace", "add", str(market)], probe)
                command(f"{phase}-install", ["plugin", "add", "metadata-fixture@metadata-market"], probe)
            if body_probe:
                last = root / f"{phase}.last-message"
                command(phase, ["exec", "--skip-git-repo-check", "-s", "read-only",
                                "-m", model or "gpt-5.6-luna", "-o", str(last), prompt], probe)
                output = last.read_text()
            else:
                output = rendered_prompt(command(phase, ["debug", "prompt-input"], probe))
        else:
            args = ["-p"]
            if harness == "claude":
                args += ["--session-id", session, "--model", model or "haiku",
                         "--max-budget-usd", "1"]
            else:
                args += ["--trust", "--sandbox", "disabled", "--mode", "ask",
                         "--output-format", "text"]
                if model:
                    args += ["--model", model]
            if installed or body_probe:
                args += ["--plugin-dir", str(plugin)]
            # Claude's --plugin-dir accepts multiple values: the
            # delimiter prevents them consuming the positional prompt.
            output = command(phase, [*args, "--", prompt], probe)
            if not output.strip():
                raise RuntimeError("empty model response")
            if not body_probe:
                audit(harness, probe, session)
        if body_probe:
            from test_skill_body import audit_body
            evidence = audit_body(harness, probe, session, name, body, installed, output)
            write_json(root / f"{phase}.audit.json", evidence)
        else:
            check_metadata(output, name, token, body, installed)
    return {"status": "pass", "version": version,
            "model": (model or ("haiku" if harness == "claude" else "harness default"))
                     if harness != "codex" else (model or "gpt-5.6-luna" if body_probe else None),
            "evidence": "body recovery + conversation delivery audit" if body_probe else (
                "rendered prompt" if harness == "codex" else "token recovery + no-tool conversation audit"),
            "name": name, "description": description}


def main(body_probe=False):
    parser = argparse.ArgumentParser(description=("Skill body delivery: two live sessions per harness."
                                                 if body_probe else __doc__))
    parser.add_argument("harness", choices=["claude", "codex", "cursor", "all"])
    parser.add_argument("--model", help="live-session model override (single harness only)")
    parser.add_argument("--keep", action="store_true", help="retain private raw captures, including on success")
    args = parser.parse_args()
    if args.model and (args.harness == "all" or (args.harness == "codex" and not body_probe)):
        parser.error("--model requires a single live harness")
    root = Path(tempfile.mkdtemp(prefix="skill-body-" if body_probe else "skill-metadata-", dir="/tmp"))
    results = {}
    try:
        for harness in (["codex", "claude", "cursor"] if args.harness == "all" else [args.harness]):
            try:
                results[harness] = run_harness(harness, root / harness, args.model, body_probe)
            except (RuntimeError, OSError, ValueError, sqlite3.Error) as exc:
                results[harness] = {"status": "fail", "reason": str(exc)}
            print(f"{harness}: {json.dumps(results[harness])}", flush=True)
        write_json(root / "results.json", results)
        return 1 if any(r["status"] == "fail" for r in results.values()) else (
            77 if all(r["status"] == "skip" for r in results.values()) else 0)
    finally:
        if args.keep:
            print(f"Private captures retained: {root}", flush=True)
        else:
            shutil.rmtree(root)


if __name__ == "__main__":
    raise SystemExit(main())
