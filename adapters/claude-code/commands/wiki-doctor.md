---
description: Self-check that the llm-wiki plugin is wired up correctly in this repo.
---

# /wiki-doctor — connectivity self-check

Print a green/red checklist. For each item show OK or FAIL and a one-line reason.

1. **Plugin root** — `${CLAUDE_PLUGIN_ROOT}` is set and contains `plugin.json`.
2. **Gate files** — `${CLAUDE_PLUGIN_ROOT}/core/agents/{verification-gate,discipline-gates,wiki-write-protocol}.md` all present.
3. **Hooks registered** — `hooks.json` present with SessionStart and PostToolUse declared.
4. **Wiki attached** — `.llm-wiki/` exists, is its own git repo, its remote matches `<origin>.wiki.git`, and it is fast-forwardable.
5. **KG deps** — `python3 -c "import rdflib, pyshacl, yaml"` succeeds and `core/scripts/kg/build-graph.sh` is executable.
6. **Remote reachable** — `git -C .llm-wiki ls-remote` succeeds; `wiki_push` dry-run clean.
7. **Orientation dry-run** — run `${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh` and echo exactly what it would inject (orientation + index + last 5 log entries), so the last-5-log is eyeballable in this real repo.

End with a pass/fail count.
