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
- **State-2 (`--github`) attach validated** end to end against the real `chrissweet/llm-wiki-vision` GitHub wiki. `ensure-wiki.py` (SessionStart auto-clone) cleanly clones the fully-populated wiki into `.llm-wiki/`: silent on success, no scaffolding, zero tracked-file changes. `/wiki-init --github` also attaches and adds the gitignore line (with the create-mode caveat in TODO 1).
- **Install validated**: `claude plugin validate` passes for both the marketplace and the plugin manifest; a local `marketplace add` → `install` → `details` → `uninstall` cycle confirms the plugin loads enabled with 5 commands, 3 skills, and both hooks (SessionStart + PostToolUse) registered (~438 always-on tokens).
- **Packaging**: `core/` is now committed into `adapters/claude-code/core/` (not gitignored) so the marketplace install is self-contained; root `core/` stays the edit-canonical copy and `package.sh` re-syncs it. Only the KG `build/` output is ignored.
- **State-2 SCHEMA-safe attach**: `init-wiki.sh --github` re-detects mode after the clone, so attaching to an already-populated wiki runs *update* mode (append-missing-only), never overwriting a customized SCHEMA. Verified against llm-wiki-vision (switches to update mode; no tracked-file changes).
- **`ensure-wiki.py` polished and validated**: ensures the `.llm-wiki/` gitignore line on attach (so a fresh-machine auto-clone adds it without `/wiki-init`), and distinguishes state-3 (no GitHub wiki → prompt to create the first page at `.../wiki/_new`, no attach) from an existing-wiki clone failure. All three paths tested.

## TODO (next build session)

1. **Staging-dir ignore (minor)**: `ensure-wiki.py`'s atomic clone stages in a sibling `.ensure-wiki-*.wiki` dir; cover it with `.gitignore` (or rename the prefix) so it is never briefly tracked under the `.llm-wiki/` model.
2. **Packaging drift guard**: `core/` is committed into the adapter and installs correctly, but root `core/` and `adapters/claude-code/core/` can drift. Add a pre-commit/CI check that they are in sync (run `package.sh`, fail on a dirty tree), and confirm `${CLAUDE_PLUGIN_ROOT}/core/...` resolves in a real installed session.
3. **Tests**: port from upstream `scripts/test/tests/` the `session-start-hook`, `ensure-wiki` (clone/update mechanics), `adopt-apply-github-wiki-*`, `wiki-write-protocol`, and `wiki-reciprocity` suites; adapt paths to `.llm-wiki/`. Add L1 `claude plugin validate` + a path-integrity check.
4. **Executability**: confirm hooks/scripts are `chmod +x` and that the `hooks.json` command forms run under Claude Code.
5. **`guidance.md`** (ported from `claude-md-snippet.md`) is the memory-boundary / wiki-maintenance text folded into the SessionStart hook; review its wording for the plugin context (it still reads as a `CLAUDE.md` snippet).
6. **Edge case to verify**: on a repo with the Wiki feature *disabled* (not just empty), confirm `.wiki.git` fails cleanly to state-3 and never serves/attaches the main repo. (In testing, an existing wiki correctly returned its own `master`/`Home.md`, distinct from the main repo, so no quirk was observed, but the disabled-feature case is unconfirmed.)

## Not in v1 (deferred)

- MCP server (`mcp/`).
- Cursor adapter (`.cursor/rules/*.mdc` already exist upstream, easy v2).
- Features-as-plugins (`features/agent-comms`), the upstream feature-flag subsystem.
