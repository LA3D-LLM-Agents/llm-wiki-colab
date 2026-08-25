# Plugin design

## Opt-in model

The plugin installs per machine (user scope).
Its SessionStart hook is a strict no-op unless a repo has opted in.
Opt-in is the presence of a gitignored `.llm-wiki/` folder.
The hook never auto-clones, even when the repo has a GitHub wiki.
Attaching a repo to a wiki is exclusively `/wiki-init`'s job.

This exists because a globally-installed plugin must not create state in arbitrary repos.
A plugin that auto-clones on any repo with a GitHub wiki would silently create a `.llm-wiki/` folder the user never asked for.

## Attach semantics

Attach is clone plus a `.gitignore` line plus a report, with zero commits.
Migrations and convention drift are `/wiki-lint`'s concern, never a silent attach side effect.
Attaching to an already-populated wiki runs in update mode (append-missing-only) rather than overwriting a customized SCHEMA.
A second `/wiki-init` run leaves `HEAD` unchanged and the tree clean.

## SessionStart delivery

The hook emits one JSON object.
The user-facing banner goes in the top-level `systemMessage` field, because hook stdout is model context, not a user-visible channel.
`hookSpecificOutput.additionalContext` carries orientation, guidance, the index, and the last five log entries.
The orientation explicitly frames this content as already read, so the model does not redundantly re-read the index file during the session.
The no-wiki case stays silent, consistent with the opt-in model.

## `/wiki-doctor` semantics

Structural checks (plugin root, gates, hooks, `.llm-wiki/` attachment) are pass/fail.
Missing optional KG dependencies or no network are warnings, not failures.
A clean install exits 0.

## Federation

`/wiki-ask` consults a federated agent's wiki: it clones the remote wiki to a local cache, self-injects a query preamble, and operates in direct mode only, with the agent choosing which peer to ask.

`/wiki-enroll` publishes this repo to the federation: an agent card plus a discovery topic.

Federation skills depend on `jq`, `curl`, and `gh`.

## Every component is a skill

The plugin ships skills only, no commands.
A Claude Code command is a skill with `disable-model-invocation: true`: the user invokes it as `/wiki-init` exactly as before, and the model never picks it up on its own.
Argument substitution survives the move, so `/wiki-ask <agent> "<question>"` still reaches `$ARGUMENTS`.

`wiki-init`, `wiki-doctor`, `wiki-ask`, and `wiki-enroll` carry `disable-model-invocation: true` because each one runs a script with side effects that the user should be the one to trigger.
`wiki-experiment`, `wiki-source`, and `wiki-lint` omit the key and stay model-invocable, which is what they already did as skills.

Codex has no command component at all and silently drops any command using `$ARGUMENTS` during its install-time migration, so a command-shaped `wiki-ask` would vanish for Codex consumers with no error at publish time.
Shipping skills is what makes one source tree serve both harnesses.

The invocation surface still differs per harness.
Claude exposes each skill flat as `/wiki-init`; Codex namespaces it under the plugin name as `llm-wiki:wiki-init`, invoked `@llm-wiki:wiki-init` (probed, codex-cli 0.147.0).
Text that names the slash form, such as the SessionStart guidance and the wiki templates, is Claude-native wording that a Codex model receives verbatim and must translate.

## Hook behavior on Codex

Probed on codex-cli 0.147.0 against the emitted tree, with plugin hooks force-trusted by `--dangerously-bypass-hook-trust`.

`hookSpecificOutput.additionalContext` from `hooks/session-start.sh` reaches the model.
In a repo with a `.llm-wiki/`, the model quoted back index and log content that exists nowhere but the hook's output, without opening a file.
The top-level `systemMessage` banner does not appear in a `codex exec` transcript; treat the user-visible banner as a Claude affordance.

`hooks/ensure-wiki.py` and `hooks/session-start.sh` both run to completion, and neither reads stdin, so Codex's superset SessionStart payload changes nothing for them.

A Codex `PostToolUse` payload for `apply_patch` carries `tool_input.command` holding the patch text and no `file_path` field, which is why `hooks/posttooluse.sh` reads the `*** Add File:` / `*** Update File:` / `*** Move to:` markers when `file_path` is absent.
A shell write reports `tool_name` as `Bash`, the same spelling Claude uses, not `shell`.

None of this changes the trust gate: without the bypass flag, plugin hooks on Codex are discovered and silently skipped, and `codex exec` has no approval flow.

## Hook behavior on Cursor

Probed on cursor-agent 2026.08.11 against the emitted tree, installed by copy into `~/.cursor/plugins/local/`.

A plugin-shipped `sessionStart` hook fires in the CLI and its `additional_context` reaches the model's context.
That is how orientation is delivered on Cursor, and it sets the minimum supported version: 2026.08.11.
The hook is fire-and-forget, so nothing it does can block or delay session creation, and a failure costs orientation rather than the session.

Cursor's hooks file is a different dialect, not a variant of Claude's.
Event names are lowercase, each event holds a flat list of hook definitions rather than matcher groups, and the file carries a schema `version`.
The emitter therefore writes the Cursor file outright instead of deriving it from the Claude one, and the `sessionStart` entry runs an adapter, `hooks/cursor-session-start.sh`, rather than the shared hook directly.
The adapter exports `CLAUDE_PLUGIN_ROOT`, runs `ensure-wiki.py` and `session-start.sh` in the order Claude's manifest wires them, and translates `hookSpecificOutput.additionalContext` into `additional_context`.
The `systemMessage` banner has no Cursor counterpart and is dropped; the user-visible banner stays a Claude affordance.

Two facts force the adapter to exist rather than the hook being wired directly.
`${CURSOR_PLUGIN_ROOT}` expands in a hooks.json command string and nowhere else, so both adapters are handed their own root as `argv[1]`.
A hook process also receives `CURSOR_PLUGIN_ROOT` and `CLAUDE_PLUGIN_ROOT` as environment variables, which is the fallback when `argv[1]` is missing.
The hook process starts with its working directory at the plugin root rather than the workspace, while `session-start.sh` decides whether a repo has opted in by testing `.llm-wiki` against `$PWD`, so the adapter changes directory first: `CURSOR_PROJECT_DIR`, then the payload's `workspace_roots[0]`, then the inherited working directory.

`disable-model-invocation` in a skill's frontmatter causes Cursor to suppress that skill entirely: it is not listed and cannot be invoked by anyone, including the user.
The key is therefore stripped from the Cursor subtree, which makes `wiki-init`, `wiki-doctor`, `wiki-ask`, and `wiki-enroll` model-invocable there.
That is the same trade Codex already makes, for a different reason: Codex ignores the key, Cursor honors it by deleting the skill.

A second `preToolUse` entry, matched to `Shell`, puts the plugin root into the shell the agent runs a skill's commands in.
It returns `updated_input` with `export CLAUDE_PLUGIN_ROOT=<root>; ` prefixed onto the command, and the rewritten command is what executes.
Nothing else reaches that process.
`${CLAUDE_PLUGIN_ROOT}` is not expanded in a skill body, `sessionStart`'s `env` output propagates to later hook processes in the session but not to the agent's shell, and the install path is keyed on a content hash so it cannot be baked in at build time.
Without the hook, a body that shells out through the variable fails with exit 127 on `bash "/core/scripts/wiki-doctor.sh"`; with it, `wiki-doctor` reports its root as resolved from `CLAUDE_PLUGIN_ROOT` and exits 0 (verified against cursor-agent 2026.08.11, both directions).

Cursor skill bodies are therefore byte-identical to the Claude subtree's, and only frontmatter routes per harness.

The hook fires on every `Shell` call for as long as the plugin is installed, including commands that have nothing to do with the wiki.
What it does to them is one variable export followed by the original command byte for byte, so the rewrite is semantically inert.
It fails open: an unparseable payload, a non-`Shell` tool, or a missing plugin root all emit a bare `{"permission": "allow"}` and the command runs unmodified.
It never denies and never exits 2.
`core/scripts/wiki-doctor.sh` still falls back to its own location when the variable is unset, which keeps the doctor able to diagnose the case where the hook did not fire.

The skill namespace is flat, as Claude's is: a skill appears as `wiki-init`, not namespaced under the plugin.
Two installed plugins shipping the same skill names collide.

`postToolUse` is not wired on Cursor.
`hooks/posttooluse.sh` ships in the subtree as a byte-identical shared file but nothing invokes it, so the verification-gate advisory is not delivered there.

Cloud agents get no `sessionStart` at all.
Cursor's own documentation lists the hook as unavailable there, on the grounds that a cloud session would fire it after the first write rather than at true session start.
A cloud agent therefore gets the plugin's skills and no wiki orientation.

Cursor silently ignores symlinks inside an installed plugin, which is why every emitted subtree contains real files only and the build asserts that.

## Open verification items

Deferred work and unconfirmed behavior are collected in [deferred.md](deferred.md).
