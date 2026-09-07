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

Every publish commit records the version, the source ref, and the versions of the tools that produced it in its message, so a published tree can always be traced back to the commit and toolchain it came from.

## Multi-ecosystem target

`main` will eventually carry per-platform subtrees: `claude/`, `codex/`, `cursor/`, and an `antigravity/` tree.
Antigravity has no marketplace concept of its own, so its tree is installed by local path rather than through a catalog.
Each platform's catalog points only at its own subtree, and each platform gets a native manifest emitted for it.
The isolation between subtrees is structural, not conventional: each harness copies only the directory its own catalog references into its install cache, and Codex's manifest fallback chains operate per directory, so a fallback cannot jump between subtrees.
See [manifest-resolution.md](manifest-resolution.md) for the resolution details.

The Claude, Codex, and Cursor emitters all exist as of this build; Antigravity does not.
The three emitters share one spine, `emit_plugin_subtree` in `build/assemble.py`: copy the plugin tree, prune the foreign manifest dir, write the native manifest, apply the harness's hook transforms, strip skill frontmatter to that harness's keys.
Each harness parameterizes the spine with its manifest writer and hook transforms; the catalog writers stay concrete because their schemas share nothing.
The extraction was proven byte-identical against a pre-change build, comparing both content and permission bits, because a content diff alone cannot see a dropped executable bit on the Cursor adapters.

## Publishing policy

`VERSION` at the repository root is the single version of the artifact.
Every version that ships is stamped from it: the Claude plugin manifest, the Codex plugin manifest, `CITATION.cff`, a `VERSION` file at the artifact root, and the publish commit message.
No version is written by hand anywhere else, and a source manifest that carries its own version field fails the build.
The plugin description follows the same rule.
One template in the build is stamped into every plugin manifest and catalog entry, differing only in the harness it names, and a source manifest that carries its own description field fails the build.

Publishing is gated on a bump.
A publish whose assembled tree differs from the target branch's current tree, and whose version has not increased over the version that branch already records, is refused.
Codex refreshes an install only when the manifest version changes, so a changed tree published under an unchanged version reaches no Codex user, while Claude installs, keyed by commit SHA, would receive it.
That divergence is what the gate exists to prevent.

The gate applies to every branch, not only to `main`.
A gate that runs only on the branch nobody publishes to daily is a gate nobody has watched work.
The one waiver is bootstrap: a parent that records no version at all, neither a `VERSION` file nor an emitted plugin manifest in any known layout, publishes with a `bootstrap:` line and no comparison.

The emitted README records the source commit, so any change on `src` changes the artifact tree.
In practice that means every publish needs a version bump, including a documentation-only one.

`--force-version` overrides the gate on a throwaway branch and is refused for `main`.
`--skip-gates` skips the behavior suite only; it never skips the version gate.

## Install identity invariants

The marketplace name `llm-wiki-colab` and the plugin name `llm-wiki` are the install identity for existing users.
Neither name may change.

The names must also stay identical across every harness catalog, not merely stable over time.
Cursor imports Claude-installed plugins by default and deduplicates on a `marketplaceName/pluginName` key, so identical names collapse a dual-harness user's install to a single copy (static analysis, Cursor 3.12.30).
Renaming either name per harness breaks that key: the user gets two same-named skill sets and both copies' hooks fire.
