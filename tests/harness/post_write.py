"""Post-write fixture hooks and advisory-delivery evidence."""

import json
import re

from .conversation import Conversation
from .harness_support import plugin_fixture, write_json

TOKEN = re.compile(r"POSTWRITE-[0-9a-f]{32}")
CONTENTS = "after probe\n"


def make_post_write_fixture(run, case, tool, target, *, emit):
    run.market, run.plugin = plugin_fixture(run.root, run.harness)
    capture = run.root / f"{case}.hook.jsonl"
    script = run.plugin / "hooks/post-write.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "import json, secrets, sys\nfrom pathlib import Path\n"
        "payload = json.load(sys.stdin)\n"
        f"target = Path({str(target)!r})\n"
        "observed = target.read_text() if target.is_file() else None\n"
        "token = 'POSTWRITE-' + secrets.token_hex(16)\n"
        f"emit = {emit!r}\n"
        f"with Path({str(capture)!r}).open('a') as capture:\n"
        "    capture.write(json.dumps({'payload': payload, 'token': token, 'emitted': emit, 'observed': observed}) + '\\n')\n"
        "context = 'Post-write advisory token: ' + token if emit else ''\n"
        + ("print(json.dumps({'additional_context': context}))\n" if run.harness == "cursor" else
           "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': context}}))\n")
    )
    variable = "CURSOR_PLUGIN_ROOT" if run.harness == "cursor" else "CLAUDE_PLUGIN_ROOT"
    hook = {"type": "command", "command": f'python3 "${{{variable}}}/hooks/post-write.py"'}
    config = ({"version": 1, "hooks": {"postToolUse": [{"matcher": tool, **hook}]}}
              if run.harness == "cursor" else
              {"hooks": {"PostToolUse": [{"matcher": tool, "hooks": [hook]}]}})
    write_json(run.plugin / "hooks/hooks.json", config)
    return capture


def post_write_evidence(conversation: Conversation, output, captures, tool, target, *, emitted,
                        request_context: Conversation | None = None):
    if not output.strip():
        raise RuntimeError("empty model response")
    if len(captures) != 1:
        raise RuntimeError("expected exactly one matching post-write hook invocation")
    capture = captures[0]
    payload = capture.get("payload", {})
    if payload.get("tool_name") != tool:
        raise RuntimeError("hook payload does not identify the requested write tool")
    if payload.get("hook_event_name") not in ("PostToolUse", "postToolUse"):
        raise RuntimeError("not a post-tool hook event")
    if target.name not in json.dumps(payload.get("tool_input")):
        raise RuntimeError("hook payload does not reference the target")
    if capture.get("observed") != CONTENTS or target.read_text() != CONTENTS:
        raise RuntimeError("hook did not observe the completed write")
    token = capture.get("token")
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise RuntimeError("missing or malformed advisory token")
    if capture.get("emitted") is not emitted:
        raise RuntimeError("hook emission mode does not match the control")
    if not conversation.calls:
        raise RuntimeError("no recorded tool invocation")
    # Only target reads/writes are allowed. A read of hook code or captures
    # would supply an alternate route to the token and invalidate the probe.
    if any(target.name not in call.arguments for call in conversation.calls):
        raise RuntimeError("tool activity beyond the requested target")
    if any(TOKEN.search(call.arguments) for call in conversation.calls):
        raise RuntimeError("advisory token reused in a tool call")
    context = request_context if request_context is not None else conversation
    incoming = "\n".join(text for _, text in context.incoming)
    if emitted:
        if token not in incoming:
            raise RuntimeError("advisory absent from incoming context")
        if token not in output:
            raise RuntimeError("advisory token not recovered")
    elif TOKEN.search(incoming) or TOKEN.search(output):
        raise RuntimeError("advisory leaked from silent hook control")
    return {"hook_executed": True, "write_completed_before_hook": True,
            "advisory_received": emitted, "tool": tool,
            "evidence": "API request + transcript" if request_context is not None else "conversation record"}
