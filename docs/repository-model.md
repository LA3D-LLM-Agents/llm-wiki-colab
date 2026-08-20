# Repository model

## Branch model

`main` is the default branch.
It is a protected, machine-generated artifact branch: nothing is hand-edited there.
Its history is append-only.
Claude Code keys plugin installs by commit SHA, so published history on `main` must never be rewritten.
A bad publish is corrected by publishing a new build on top of it, never by force-push.

`src` is the development branch.
All human work, including pull requests, lands on `src` and targets `src`.

## Why main stays the default branch

Install UX depends on it.
`/plugin marketplace add owner/repo` resolves the default branch on every platform that supports it.
Branch-ref syntax differs per platform and fails silently on some of them: Cursor treats `owner/repo#branch` as a request for the default branch and reports success even though the named branch was never resolved.
Keeping `main` as the default branch means one plain `owner/repo` string works everywhere, with no platform-specific branch syntax to maintain or document.

## The build seam

One assembly script emits the artifact tree.
It is the single definition of what `main` contains.
The same script runs locally, writing to `build/out/`, and in CI, writing what gets published.

Everything that validates or installs the plugin operates on build output, never on the source tree.
The source tree deliberately carries no `.claude-plugin/marketplace.json`, so a `src` checkout is not directly installable.
The marketplace catalog exists only in build output.

## Publishing

One publish script turns a source commit into a branch commit.
It assembles the artifact tree into a scratch directory, runs the behavior suite against that tree as a gate, and appends a single commit of pure build output to the target branch.
Staging happens in a temporary index, so the working copy and the checked-out ref are never touched.

Publishing to `main` requires an explicit flag; every other branch publishes without one.
The script only moves a local ref.
Pushing the branch is the caller's responsibility.

Every publish commit records the source ref and the versions of the tools that produced it in its message, so a published tree can always be traced back to the commit and toolchain it came from.

## Multi-ecosystem target

`main` will eventually carry per-platform subtrees: `claude/`, `codex/`, `cursor/`, and an `antigravity/` tree.
Antigravity has no marketplace concept of its own, so its tree is installed by local path rather than through a catalog.
Each platform's catalog points only at its own subtree, and each platform gets a native manifest emitted for it.

The Claude and Codex emitters both exist as of this build; Cursor and Antigravity do not.
The two emitters are deliberately near-duplicates. Generalizing across them is deferred until the shared abstraction can be extracted from concrete instances rather than guessed at.

## Publishing policy

While Claude is the only platform, publishing is continuous: every green `src` build publishes to `main`.
Claude installs are keyed by commit SHA, so every publish is naturally versioned and safe to ship without a separate release step.

Codex keys its cache on manifest semver instead of commit SHA.
Once the Codex emitter lands, publishing becomes gated on a version bump rather than continuous.

## Install identity invariants

The marketplace name `llm-wiki-colab` and the plugin name `llm-wiki` are the install identity for existing users.
Neither name may change.
