---
description: Health-check the wiki for orphans, dead links, stale claims, missing frontmatter.
---

You are running a health check on the wiki at `.llm-wiki/`. Defer to `SCHEMA_<repo>.md` for the precise conventions.

Full procedure: see `the wiki-lint skill`. Summary:

1. Read `index_<repo>.md` to get the canonical list of pages.
2. List all `.md` files in the wiki directory.
3. Scan systematically for each check below and collect findings:
   - **Orphan pages** (no inbound links from other pages or index)
   - **Dead links** (`[Display](Page)` or `[[Page]]` pointing to non-existent files)
   - **Stale claims** (superseded by newer pages or current code/results)
   - **Missing frontmatter** (no block at top, or missing `type:` / `up:`)
   - **`type: untyped`** pages whose proper type is now obvious
   - **Missing concept pages** (concepts mentioned in multiple bodies without their own page)
   - **Missing cross-references** in either direction (if A → B, B should → A) — enumerate mechanically with `python3 ${CLAUDE_PLUGIN_ROOT}/core/scripts/wiki-reciprocity.py .llm-wiki/` (lists one-way links; exempts special files and `hub: true` pages)
   - **Index gaps** (pages in wiki but not listed in `index_…md`)
   - **Naming convention** deviations (should be `Title-Case-Hyphenated.md`)
   - **Special-file integrity** (`Home_…`, `index_…`, `log_…`, `SCHEMA_…`, `Home.md` redirect)
4. Report findings to the user grouped by check type, with one or two example pages per finding.
5. Ask which findings to fix in this pass. Lint is incremental.
6. For accepted fixes, apply them with cross-reference repair in both directions, update `index_<repo>.md` as needed, and append a `## [YYYY-MM-DD] lint | Subject` entry to `log_<repo>.md`. The first bullet of that entry is the attribution line `- by: <name> via claude-code`, where `<name>` is the output of `git config user.name` in the wiki repo (read it, do not invent it). See "Log Entry Attribution" in `SCHEMA_<repo>.md`.
7. Optionally rebuild the knowledge graph: `${CLAUDE_PLUGIN_ROOT}/core/scripts/kg/build-graph.sh`.
8. **Finish the cycle.** Commit in the wiki's own git repo in two steps, without asking. One commit per log entry keeps `git blame` on the log a faithful per-entry record (see "Log Entry Attribution" in SCHEMA):
    ```
    git -C .llm-wiki add <lint-fix-and-index-files-by-name>
    git -C .llm-wiki commit -m "lint: <summary>"
    git -C .llm-wiki add log_<repo>.md
    git -C .llm-wiki commit -m "log: lint <summary>"
    ```
    Local commits are reversible. Push only if the user requests. **When pushing, follow the procedure at `${CLAUDE_PLUGIN_ROOT}/core/agents/wiki-write-protocol.md`** rather than plain `git push`.

Honest reporting: do not paper over contradictions. If two pages disagree and current code/results decide between them, update the loser and link to the winner.
