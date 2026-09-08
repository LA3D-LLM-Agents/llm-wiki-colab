#!/usr/bin/env python3
"""Run installed XX-name.py stages in order and emit one SessionStart response.

Each stage exports run(state), mutates the shared dictionary, and returns no
output. Set state["stop"] to skip remaining stages. Only this coordinator emits
harness JSON. Paths are resolved from this file, never the caller's plugin env.
"""
import json
from pathlib import Path
import runpy
import sys


def main():
    hooks = Path(__file__).resolve().parent
    state = {"plugin_root": hooks.parent, "project_root": Path.cwd(),
             "warnings": [], "context": [], "banner": "", "stop": False}
    for stage in sorted((hooks / "session-start.d").glob("[0-9][0-9]-*.py")):
        try:
            runpy.run_path(str(stage))["run"](state)
        except Exception as exc:
            state["warnings"].append(
                f"llm-wiki: {stage.name} failed ({type(exc).__name__}); "
                "wiki startup is incomplete.")
            break
        if state["stop"]:
            break
    context = "\n\n".join(state["warnings"] + state["context"])
    if context:
        banner = "; ".join(filter(None, [state["banner"], *state["warnings"]]))
        json.dump({"systemMessage": banner, "hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": context}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
