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
- `core/init-wiki.sh` adapted for the plugin model and **create-mode smoke-tested**: lib-source path fixed, `WIKI_DIR` → `.llm-wiki/`, `CLAUDE.md` writer removed, WIKI-INDEX registration removed, `.gitignore` line auto-added. Verified in a fresh repo: builds `.llm-wiki/` with namespaced files; the only project footprint is the `.gitignore` line; no `CLAUDE.md` or `WIKI-INDEX` written.

## TODO (next build session)

1. **`/wiki-init` state-2 (`--github`) validation**: the create / local-init path is done and tested. Validate `init-wiki.sh --github` (clone an existing GitHub wiki into `.llm-wiki/`) against a repo that actually has a GitHub wiki, and confirm the command's three-state ensure/attach flow end to end.
2. **`ensure-wiki.py` state-3 enhancement**: distinguish "no GitHub wiki yet" (empty `git ls-remote`) from other clone failures and emit the "create the first page" prompt (currently a generic "clone it" nudge). Also cover the staging dir (`.ensure-wiki-*.wiki`) with `.gitignore` under the `.llm-wiki/` model.
3. **Packaging**: `adapters/claude-code/package.sh` copies `core/` into the adapter (gitignored). Confirm `${CLAUDE_PLUGIN_ROOT}/core/...` resolves post-install; wire into CI.
4. **Tests**: port from upstream `scripts/test/tests/` the `session-start-hook`, `ensure-wiki` (clone/update mechanics), `adopt-apply-github-wiki-*`, `wiki-write-protocol`, and `wiki-reciprocity` suites; adapt paths to `.llm-wiki/`. Add L1 `claude plugin validate` + a path-integrity check.
5. **Executability**: confirm hooks/scripts are `chmod +x` and that the `hooks.json` command forms run under Claude Code.
6. **`guidance.md`** (ported from `claude-md-snippet.md`) is the memory-boundary / wiki-maintenance text folded into the SessionStart hook; review its wording for the plugin context (it still reads as a `CLAUDE.md` snippet).

## Not in v1 (deferred)

- MCP server (`mcp/`).
- Cursor adapter (`.cursor/rules/*.mdc` already exist upstream, easy v2).
- Features-as-plugins (`features/agent-comms`), the upstream feature-flag subsystem.
