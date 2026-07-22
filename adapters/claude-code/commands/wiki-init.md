---
description: Initialize or attach this project's llm-wiki durable memory (.llm-wiki/).
---

# /wiki-init — ensure/attach the llm-wiki

Idempotent. Never clobbers an existing wiki. Resolve the state, then act.

1. **Already attached** — if `.llm-wiki/` exists: run nothing destructive.
   `git -C .llm-wiki pull --ff-only` (best effort) and report the index plus the
   last log entry.
2. **Exists on GitHub, not local** — derive the wiki remote from `origin`
   (`<owner>/<repo>.wiki.git`) and probe `git ls-remote`. If it returns refs,
   clone it into `.llm-wiki/`, then ensure `.llm-wiki/` is in the project
   `.gitignore`.
3. **No GitHub wiki yet** — `git ls-remote` returns nothing: tell the user to
   enable the repo Wiki and create the first page at
   `https://github.com/<owner>/<repo>/wiki/_new`, then re-run. Once any page
   exists this drops to state 2.

After attach (state 1 or 2), if the wiki has no `SCHEMA_<repo>.md`, scaffold the
neutral core with `${CLAUDE_PLUGIN_ROOT}/core/init-wiki.sh --github --agent claude-code`.

Constraints: add `.llm-wiki/` to `.gitignore`; **do not** write to `CLAUDE.md`
(guidance rides the SessionStart hook); operate only on `.llm-wiki/`, never the
main repo.

Report which state was taken and the resulting wiki path.

> `core/init-wiki.sh` has been adapted for the plugin model (memory at
> `.llm-wiki/`, no `CLAUDE.md` writer, no WIKI-INDEX registration, auto-adds the
> `.gitignore` line) and smoke-tested in create mode. The `--github` clone path
> (state 2 against a real GitHub wiki) still needs an end-to-end check.
