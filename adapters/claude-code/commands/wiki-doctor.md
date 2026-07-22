---
description: Self-check that the llm-wiki plugin is wired up correctly in this repo.
---

# /wiki-doctor — connectivity self-check

Run the doctor script from the project root and report its output verbatim:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/core/scripts/wiki-doctor.sh"
```

It prints a green/red checklist, plugin root, gate files, hooks declared,
`.llm-wiki/` attachment, KG deps, remote reachability, and an orientation
dry-run showing the last log entry SessionStart would surface. Structural
failures set a non-zero exit; missing KG deps or no network are warnings.

If a structural check FAILs, help the user fix it: run `/wiki-init` if
`.llm-wiki/` is absent; reinstall the plugin if the root, gates, or hooks are
missing.
