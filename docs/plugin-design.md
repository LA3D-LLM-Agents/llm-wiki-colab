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

Federation commands depend on `jq`, `curl`, and `gh`.

## Open verification items

- A repo with the GitHub Wiki feature disabled (not merely empty) should fail cleanly to the create-first-page path and never attach the main repo. Unconfirmed.
- A live-session check that the SessionStart orientation actually appears in a real installed session. Unconfirmed.
