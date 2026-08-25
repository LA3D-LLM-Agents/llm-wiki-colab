# Deferred work

Work that was considered and intentionally postponed, with enough context to pick each item up cold.
Items move out of this file when they land or when a decision retires them.

## Build and emitters

- Make every assembled skill self-contained: no shared `core/` directory in build output.
  The source tree keeps one shared `core/`, and the emitter materializes each skill's dependencies (scripts, templates, referenced agent docs) into that skill's own directory, accepting duplication across skills in the generated tree.
  Skill bodies then reference `scripts/...` by relative path from the skill root, which is Cursor's documented skill idiom and resolves on every harness because the model knows where it read the SKILL.md.
  Applied uniformly to all three subtrees so skill bodies stay identical across harnesses.
  Consequences: the `preToolUse` plugin-root export hook can likely be retired along with all `${CLAUDE_PLUGIN_ROOT}` references in skill bodies, and `wiki-doctor` becomes trivially self-locating.
  Hook scripts are unaffected; they resolve their plugin root through hooks.json expansion and can carry their own copies of any templates they need.
- Extract the shared emitter spine across the Claude, Codex, and Cursor blocks in `build/assemble.py`.
  The shape they agree on is narrow: copy tree, prune foreign manifest dirs, write native manifest, per-harness transforms, strip frontmatter.
  The catalog writers stay concrete because their schemas share nothing.
  The extraction commit must produce byte-identical assembled output, proven with `diff -r` against a pre-change build.
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
