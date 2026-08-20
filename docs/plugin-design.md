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

## Hook behavior on Codex

Probed on codex-cli 0.147.0 against the emitted tree, with plugin hooks force-trusted by `--dangerously-bypass-hook-trust`.

`hookSpecificOutput.additionalContext` from `hooks/session-start.sh` reaches the model.
In a repo with a `.llm-wiki/`, the model quoted back index and log content that exists nowhere but the hook's output, without opening a file.
The top-level `systemMessage` banner does not appear in a `codex exec` transcript; treat the user-visible banner as a Claude affordance.

`hooks/ensure-wiki.py` and `hooks/session-start.sh` both run to completion, and neither reads stdin, so Codex's superset SessionStart payload changes nothing for them.

A Codex `PostToolUse` payload for `apply_patch` carries `tool_input.command` holding the patch text and no `file_path` field, which is why `hooks/posttooluse.sh` reads the `*** Add File:` / `*** Update File:` / `*** Move to:` markers when `file_path` is absent.
A shell write reports `tool_name` as `Bash`, the same spelling Claude uses, not `shell`.

None of this changes the trust gate: without the bypass flag, plugin hooks on Codex are discovered and silently skipped, and `codex exec` has no approval flow.

## Open verification items

- A repo with the GitHub Wiki feature disabled (not merely empty) should fail cleanly to the create-first-page path and never attach the main repo. Unconfirmed.
- A live-session check that the SessionStart orientation actually appears in a real installed Claude session. Unconfirmed.
