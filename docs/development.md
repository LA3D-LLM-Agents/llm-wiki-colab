# Development

## Toolchain

devenv.sh provisions the stable tools used for local work: `jq`, `shellcheck`, and `uv`.
devenv is a convenience, not a contract.
Every build, test, and publish script is a plain script runnable with those tools on PATH, and nothing in the repository may require the devenv shell.

Platform CLIs (`claude`, `codex`, and `cursor-agent`) are installed at their current release, outside the devenv lock.
They are the subject under test, so they must match what users actually run rather than a pinned version.
`cursor-agent` must be 2026.08.11 or newer: earlier versions do not run a plugin's own session-start hook, so the Cursor subtree cannot be exercised against them at all.

## Build and test discipline

Always build to a scratch directory and test or install the built artifact from there.
Never point a plugin host at the source tree.
Claude's `--plugin-dir` flag can bypass this and load the source tree directly; that is fine as a deliberate, occasional act, but it is not the supported development loop.

Cursor loads a local plugin from `~/.cursor/plugins/local/<name>/`.
Copy the built subtree there; do not link it.
Cursor silently ignores symlinks inside an installed plugin, so a linked tree installs as a plugin whose files are all missing.
The skill namespace is flat, so a local copy and a real install of the same plugin collide and both sets of hooks fire.
`tests/test_cursor_manifests.sh` carries a live check of this loop, gated behind `LLM_WIKI_CURSOR_SMOKE=1` because it writes into `~/.cursor/plugins/local/` and spends a model call.

## Script language conventions

Build and publish tooling is Python, run as uv single-file scripts using PEP 723 inline metadata.
Behavior tests are plain bash.

## Template hydration

Artifact-tree templates under `build/templates/` use `{{token}}` placeholders.
The build fails if any token survives unhydrated into output.

## Versioning

`VERSION` at the repository root holds one `MAJOR.MINOR.PATCH` line and is the only place a version is written by hand.
The build stamps it into every emitted manifest, so bumping is a one-file edit.

A bump is an ordinary source commit on `src`: edit `VERSION`, commit, publish.
`build/publish.py` refuses to publish a changed tree that reuses the version the target branch already carries, so a forgotten bump fails the publish rather than shipping an update Codex users never receive.

## CI and evaluation boundaries

CI runs only deterministic gates: build, validation, and behavior tests.
CI never gates on model-based evaluation.
Evaluation runs are operator-driven, since subscription auth is not reliably available in CI, and their results land as data rather than as a pass/fail signal.

## Session-start stages

The manifest registers one `hooks/session-start.py` coordinator. It loads
`hooks/session-start.d/XX-name.py` files from its installed plugin directory
in filename order. Each file exports `run(state)` and contributes to the shared
state rather than printing output. Use distinct two-digit prefixes.

The shipped stages validate attachment (`10`), maintain the checkout (`20`),
and build orientation (`30`). `state["stop"] = True` stops subsequent stages;
`warnings` and `context` accumulate strings for the final response. An unexpected
stage exception stops processing and produces a diagnostic without failing the
host session. Only the coordinator serializes harness JSON. Cursor's adapter
resolves the workspace and translates that response, retaining stage warnings.

The coordinator locates resources relative to its own file; it does not depend
on `CLAUDE_PLUGIN_ROOT`. Checkout updates retain the existing clean-tree and
fast-forward guards. They run before the index and log are read.
