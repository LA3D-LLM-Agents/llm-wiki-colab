# Deferred work

Work that was considered and intentionally postponed, with enough context to pick each item up cold.
Items move out of this file when they land or when a decision retires them.

## Build and emitters

- Make every assembled skill self-contained: no shared `core/` directory in build output.
  The source tree keeps one shared `core/`, and the emitter materializes each skill's dependencies (scripts, templates, referenced agent docs) into that skill's own directory, accepting duplication across skills in the generated tree.
  Applied uniformly to all three subtrees so skill bodies stay identical across harnesses.
  Consequences: the `preToolUse` plugin-root export hook can likely be retired along with all `${CLAUDE_PLUGIN_ROOT}` references in skill bodies, and `wiki-doctor` becomes trivially self-locating.
  Hook scripts are unaffected; they resolve their plugin root through hooks.json expansion and can carry their own copies of any templates they need.
  How each harness resolves a skill body's file references, established by probing and source inspection:
  Claude Code sets `CLAUDE_SKILL_DIR` in the shell that runs a skill's commands, holding that skill's own directory, so `${CLAUDE_SKILL_DIR}/scripts/foo.sh` expands deterministically there.
  Codex instructs the model to resolve relative references such as `scripts/foo.py` against the containing SKILL.md; this is model behavior, not textual expansion by the loader (codex-rs/ext/skills/src/catalog_prompt.rs:25).
  Cursor gives the model the SKILL.md's absolute path but nothing enforces combining it (cursor-agent 2026.08.11): a bare relative `scripts/foo.sh` failed first-try in 2 of 2 probe runs, and real-looking `${VAR}` spellings were submitted literally first (exit 127, then recovered).
  An unset-looking `$SKILL_DIRECTORY/scripts/foo.sh` placeholder worked in live testing: the model substitutes the skill directory it was given, and a literal run fails loudly on the empty expansion rather than running a silent wrong path.
  Settled: emit `${CLAUDE_SKILL_DIR}` in the Claude subtree and rewrite it to the `$SKILL_DIRECTORY` placeholder in the Codex and Cursor subtrees.
  `wiki-doctor.sh` stays unchanged by this migration; its self-location fallback and `core/agents/` gate check mean the doctor's files keep their `core/` layout in the output.
- Wire the community `cursor/plugin-template` validator (`validate-template.mjs`) as an env-gated confirmation in the test suite, never as a hard gate.
  Its known defects (line-based frontmatter parsing, object-form `source` rejected, command frontmatter required though the runtime treats it as optional) would otherwise shape the emitter around a third party's bugs.

## Cursor delivery

- Port the `posttooluse` advisory to Cursor as an `afterFileEdit` hook.
  `hooks/posttooluse.sh` ships in the Cursor subtree but is unwired; `afterFileEdit` has a different input shape (see `docs/cursor/hooks/after-file-edit.md`).
- Explore Cursor's manifest `variables` feature for team-configurable plugin settings.
  `.cursor-plugin/plugin.json` may declare a restricted JSON Schema under `variables` (top level must be `{ "type": "object", "properties": { ... } }`; only `type`, `title`, `description`, `default`, `enum`, `const`, `properties`, `required`, `items`, and common length/numeric constraints are accepted), and team admins set the values in the dashboard at install time or later via Configure.
  Values substitute as `${VAR}` placeholders into `mcp.json`; secrets never live in the plugin repo.
  Open questions: whether `${VAR}` also substitutes into hooks.json command strings or anywhere beyond MCP config, and what the cross-harness story is (Claude's analog is plugin `userConfig`, Codex has none).
  Candidate uses for llm-wiki: an auth token for cloning private wiki remotes, or an org-configurable wiki host, both currently impossible to configure per team.
- Decide whether Claude's user-visible `systemMessage` banner needs a Cursor equivalent.
  The Cursor adapter drops it; the only observed route is folding it into `additional_context`, where it becomes model-repeated rather than rendered.
- Until the self-contained-skill restructure lands, skill references to shared `core/` files sit outside the skill root, and the `preToolUse` export is what makes the shell route to them deterministic.
  New skills should phrase script references as commands rather than read-this-file pointers.

## Removed pending reimplementation

Both subsystems below were removed rather than carried, because their code and documentation still targeted the ancestor template layout.
Recover either implementation from version history; both were last present at `src` commit `6e1d4ff2`.

- Reimplement the knowledge-graph pipeline (was `core/scripts/kg/`: `build-graph.sh`/`.py`, `wiki-to-jsonld.py`, 11 curated SPARQL queries) against the current layout.
  The removed code defaulted its wiki path to the ancestor's `wiki/*.wiki/` rather than `.llm-wiki/`, and fetched ontology, shapes, and context from the LA3D GitHub Pages URL.
  The typed-edge vocabulary survives in `core/Edge-Types.md.template` and the scaffolded SCHEMA, which still frame inverse materialisation as a KG build's job, so a reimplementation has its input contract intact.
  `wiki-doctor` no longer checks KG dependencies; restore an optional-deps warning when the pipeline returns.
- Reimplement the wiki-write-protocol push wrapper (was `core/scripts/wiki-write-protocol/protocol.sh` plus the ten-scenario suite under `tests/wiki-write-protocol/` and the agent procedure doc `core/agents/wiki-write-protocol.md`).
  The wrapper provided `wiki_push` (optimistic push, fetch-merge-classify-retry on rejection, union merge for `index_*`/`log_*`, semantic-conflict deferral) and `agent_session_start` (fast-forward freshness check).
  Skills and guidance now say plain push-only-when-asked with no collision protocol, so concurrent writers to a shared wiki can conflict at push time.
  The union-merge `.gitattributes` the old README attributed to `init-wiki.sh` scaffolding was never actually written by it; a reimplementation should close that gap too.

## Verification gaps

- A repo with the GitHub Wiki feature disabled (not merely empty) should fail cleanly to the create-first-page path and never attach the main repo.
  Unconfirmed.
- A live-session check that the SessionStart orientation actually appears in a real installed Claude session.
  Unconfirmed.

## Post-publish only

- Confirm dual-harness dedup: with the plugin installed from both marketplaces, the Cursor copy should shadow the imported Claude copy on the shared `llm-wiki-colab/llm-wiki` identity.
- Set up the Cursor GitHub App (Auto Refresh) on the published repo; without it installs stay pinned to the install-time commit.
- Observe what a marketplace update actually does to a live Cursor install once Auto Refresh is active.

## Out of scope until wanted

- Cloud agents get no `sessionStart`, so they receive skills without wiki orientation; no workaround is planned.
- An Antigravity subtree.
- MCP, agents, and commands components for any harness.
