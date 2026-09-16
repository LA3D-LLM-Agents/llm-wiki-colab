# Development

## Toolchain

devenv.sh provisions the stable tools: `act`, `actionlint`, `git`, `jj`, `jq`, `shellcheck`, and `uv`.
Every build, test, and publish script is a plain script runnable with those tools on PATH, and nothing in the repository may require the devenv shell.
CI runs inside the devenv shell, so `devenv.lock` is the definition of the toolchain the gates are checked against.

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

## Releasing

Publishing happens locally, because the gates need the harness CLIs and CI has no subscription auth.
A publish to `main` also tags the source commit as `v<VERSION>`, so the tag, the `VERSION` file, and the `source-ref` trailer in the publish commit cannot disagree.
The tag lives on `src`, where the commit history is, since `main` carries one squashed build commit per release and nothing to write a changelog from.

```sh
uv run build/publish.py --branch main --allow-main
jj git push -b main
jj git push --tag v0.5.0
```

Push `main` before the tag, or push both refs atomically.
The tag push triggers CI, which reads `main`'s tip and refuses if the tag landed first.

CI never publishes.
On every push and on every release tag it runs `build/publish.py --verify origin/main --reachable-from origin/src`, which extracts the source commit that `main`'s tip records with `git archive`, rebuilds the artifact from it, and refuses unless the tree hash matches the published one.
That catches a publish made from uncommitted edits, a source commit that jj later rewrote, and a `main` moved by hand.
On a tag push it also passes `--tag`, which requires the tag to name the recorded source commit and the version the published tree carries.
A publish commit records `gates: skipped` when the suite did not run, and verify refuses such a tree.

Release notes come from the conventional commits between two release tags, rendered by git-cliff with the repository `cliff.toml`.
Commits scoped to the repository's own tooling (`ci`, `dev`, `docs`, `build`, `deps`, `act`, `tests`) and the `chore`, `docs`, `test`, and `style` types are left out, so the list holds only what a person who installs the plugin would notice.
Each entry carries the commit subject and the first sentence of the body, so a body that leads with the symptom reads as a changelog line without editing.

```sh
git-cliff --latest --strip all > notes.md
```

Write a short preamble above the generated list saying what the release means, then attach the notes to the tag with `gh release create v0.5.0 --notes-file notes.md`.
`git-cliff --unreleased --strip all` previews the next release's list before it is tagged.

## CI and evaluation boundaries

CI runs only deterministic gates: build, validation, and behavior tests.
CI never gates on model-based evaluation.
Evaluation runs are operator-driven, since subscription auth is not reliably available in CI, and their results land as data rather than as a pass/fail signal.

`.github/workflows/ci.yml` runs on every push to `src` and on pull requests.
It installs a pinned Determinate Nix and a pinned devenv, then runs `devenv test`.
The gates are the devenv tasks wired `before = [ "devenv:enterTest" ]`, so adding a gate is adding a task and needs no workflow change.
The platform CLIs are not in the devenv lock, so the checks that need them skip in CI and run only on a developer host.
Bump the devenv pin in the workflow together with the devenv used locally.

devenv captures task output and prints it only when the task fails.
A green run therefore shows one line per task, and a red run shows the whole suite output including the failing file count.

## Interpreter floors

The shipped hooks run under the user's system interpreters, not under the lock.
Stock macOS ships bash 3.2.57 and Python 3.9, so those are the floors the plugin supports.
`llm-wiki:test-floor` runs the suite once more with both floors first on PATH, so a hook that picks up a newer bash or Python feature fails here rather than on a user's machine.
bash 3.2 is built from source in `devenv.nix`, since no current distribution packages it.
Python 3.9 comes from the `nixpkgs-py39` input, pinned to the last nixpkgs release that carried it.
CI stores the bash build in the Actions cache keyed on `devenv.nix` and `devenv.lock`, so it is compiled once per lock change.

## Rehearsing CI locally

`devenv tasks run llm-wiki:ci` runs the workflow under act in the `catthehacker/ubuntu:act-latest` image, using the repository `.actrc`.
The container runs privileged, because Nix builds need to create sandboxes, and is kept between runs.
The first run installs Nix and builds the floor interpreters; later runs detect the existing install and reuse the store.
The checkout step copies the working tree into the container but never removes anything, so a file deleted or renamed on the host lingers there and can keep a stale test running.
`docker rm -f` on the `act-ci-test-*` container resets it; do that after deleting or renaming tracked files.
Never pass `--bind` to act: devenv writes profile links into `.devenv/`, and the container's store paths would replace the host's.

## Session-start stages

The manifest registers one `hooks/session-start.py` coordinator. It loads
`hooks/session-start.d/XX-name.py` files from its installed plugin directory
in filename order. Each file exports `run(state)` and contributes to the shared
state rather than printing output. Use distinct two-digit prefixes.

The shipped stages validate attachment (`10`), ensure the local Git exclude
(`15`), maintain the checkout (`20`), and build orientation (`30`).
The exclude stage and wiki-init each carry their own implementation; both use
Git's resolved `info/exclude` path and preserve existing contents.
`state["stop"] = True` stops subsequent stages;
`warnings` and `context` accumulate strings for the final response. An unexpected
stage exception stops processing and produces a diagnostic without failing the
host session. Only the coordinator serializes harness JSON. Cursor's adapter
resolves the workspace and translates that response, retaining stage warnings.

The coordinator locates resources relative to its own file; it does not depend
on `CLAUDE_PLUGIN_ROOT`. Checkout updates retain the existing clean-tree and
fast-forward guards. They run before the index and log are read.
