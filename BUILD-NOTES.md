# Build notes — llm-wiki plugin (v1 skeleton)

Scope: **v1 = Claude Code adapter only** (MCP server, Cursor adapter, and
features-as-plugins are deferred). Ported from
`crcresearch/llm-wiki-memory-template`. Design: llm-wiki-vision wiki,
*Plugin-Packaging-Architecture*.

## Done (this scaffold)

- Monorepo structure: `core/`, `adapters/claude-code/{commands,skills,hooks,.claude-plugin}`, `.claude-plugin/marketplace.json`.
- Ported verbatim from upstream: gates (`core/agents/*`), `core/scripts/{lib,wiki-write-protocol,kg}`, `core/init-wiki.sh`, `core/Edge-Types.md.template`, `core/templates/*`, the three commands and three skills.
- Authored: `plugin.json`, `marketplace.json`, `hooks.json`, `/wiki-init` and `/wiki-doctor` command specs, `README.md`, `package.sh`.
- Hooks repathed to the `.llm-wiki/` + opt-in model:
  - `hooks/session-start.sh`: **rewritten** — silent no-op unless `.llm-wiki/` exists (opt-in), derives the namespace from `origin` at runtime (no install-time `${REPO_NAME}` bake), emits orientation + guidance + index + last-5 log against `.llm-wiki/`.
  - `hooks/ensure-wiki.py`: `wiki_rel` repathed to `.llm-wiki` (keeps the production clone/attach: VCS-aware, atomic staged clone, `--ff-only` safety).
  - `hooks/posttooluse.sh`: matcher scoped to `.llm-wiki/*.md`; gate reference points at the plugin core.

## TODO (next build session)

1. **`core/init-wiki.sh` plugin surgery** (currently the upstream copy; do NOT run as-is):
   - Repath `WIKI_DIR` from `wiki/${REPO_NAME}.wiki` to `.llm-wiki`.
   - **Remove the `CLAUDE.md` create/update block** (~lines 894-963). The plugin must not write `CLAUDE.md`; guidance rides the SessionStart hook.
   - **Remove/rework the WIKI-INDEX recursive registration** (assumes a `wiki/` parent; under `.llm-wiki/` it would write `WIKI-INDEX.md` into the project root, a footprint).
   - Add `.llm-wiki/` to the project `.gitignore` (idempotent).
   - Keep the namespaced internal files (`index_<repo>.md`, etc.) and SCHEMA.
2. **`ensure-wiki.py` state-3 enhancement**: distinguish "no GitHub wiki yet" (empty `git ls-remote`) from other clone failures and emit the "create the first page" prompt (currently a generic "clone it" nudge). Also cover the staging dir (`.ensure-wiki-*.wiki`) with `.gitignore` under the `.llm-wiki/` model.
3. **Packaging**: `adapters/claude-code/package.sh` copies `core/` into the adapter (gitignored). Confirm `${CLAUDE_PLUGIN_ROOT}/core/...` resolves post-install; wire into CI.
4. **Tests**: port from upstream `scripts/test/tests/` the `session-start-hook`, `ensure-wiki` (clone/update mechanics), `adopt-apply-github-wiki-*`, `wiki-write-protocol`, and `wiki-reciprocity` suites; adapt paths to `.llm-wiki/`. Add L1 `claude plugin validate` + a path-integrity check.
5. **Executability**: confirm hooks/scripts are `chmod +x` and that the `hooks.json` command forms run under Claude Code.
6. **`guidance.md`** (ported from `claude-md-snippet.md`) is the memory-boundary / wiki-maintenance text folded into the SessionStart hook; review its wording for the plugin context (it still reads as a `CLAUDE.md` snippet).

## Not in v1 (deferred)

- MCP server (`mcp/`).
- Cursor adapter (`.cursor/rules/*.mdc` already exist upstream, easy v2).
- Features-as-plugins (`features/agent-comms`), the upstream feature-flag subsystem.
