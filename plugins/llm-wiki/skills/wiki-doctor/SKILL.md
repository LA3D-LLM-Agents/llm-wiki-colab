---
name: wiki-doctor
description: Self-check that the llm-wiki plugin is wired up correctly in this repo. Use when the wiki seems inactive, hooks are not firing, or a fresh install needs verifying.
disable-model-invocation: true
---

Run the doctor script from the project root and report its output verbatim:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/wiki-doctor.sh"
```

It prints a green/red checklist, plugin root, gate files, hooks declared, `.llm-wiki/` attachment, remote reachability, and an orientation dry-run showing the last log entry SessionStart would surface.
Structural failures set a non-zero exit; no network is a warning.

If a structural check FAILs, help the user fix it: run `/wiki-init` if `.llm-wiki/` is absent; reinstall the plugin if the root, gates, or hooks are missing.
