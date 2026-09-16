---
name: cut-release
description: Cuts a plugin release. Runs the live harness checks, bumps VERSION, publishes main, tags the source commit, verifies the rebuild, pushes, and creates the GitHub release with git-cliff notes.
argument-hint: "[version]"
arguments: version
disable-model-invocation: true
allowed-tools: Bash(cat VERSION) Bash(command -v *) Bash(claude --version) Bash(codex --version) Bash(cursor-agent --version) Bash(ls *) Bash(git status *) Bash(git log *) Bash(git tag --list *) Bash(git rev-parse *) Bash(git merge-base *) Bash(git fetch *) Bash(git ls-remote *) Bash(gh run *) Bash(git-cliff *)
---

# Cut a release

The operator is the human in this conversation.
The target version is `$version`; when it is empty, propose one in step 2 and get the operator's agreement before continuing.
Run every command from the repository root inside `devenv shell`.
Use plain git; if the checkout uses another version control front end, do the same operations its way.

Snapshot at invocation, before any fetch:

```!
echo "VERSION: $(cat VERSION)"
echo "newest release tags: $(git tag --list 'v*' --sort=-v:refname | head -3 | tr '\n' ' ')"
echo "working tree: $(git status --porcelain | head -5 | tr '\n' ' ')"
```

Reproduce this checklist in your first reply and tick items as they complete:

```text
Release progress:
- [ ] Step 1: Sync and check the starting state
- [ ] Step 2: Choose the version
- [ ] Step 3: Run the live checks
- [ ] Step 4: Bump VERSION and preview the notes
- [ ] Step 5: Publish
- [ ] Step 6: Verify locally
- [ ] Step 7: Push main and the tag
- [ ] Step 8: Watch the tag run
- [ ] Step 9: Create the GitHub release
- [ ] Step 10: Confirm delivery
```

## Step 1: sync and check the starting state

```sh
git fetch origin --tags
git switch src
git merge --ff-only origin/src
git fetch origin main:main
git status --porcelain
git log -1 --format=%B main
```

Only proceed when all of these hold; otherwise stop and report which one failed.

- Every command succeeded, so neither branch had diverged from the remote.
- `git status --porcelain` printed nothing.
- The newest `vX.Y.Z` tag equals the version in `VERSION`.
- `git merge-base --is-ancestor vX.Y.Z src` exits 0.
- `main`'s message has a `source-ref:` trailer equal to `git rev-parse vX.Y.Z^{commit}`.
- `gh run list --workflow ci --branch src --limit 1` shows `completed success`.

## Step 2: choose the version

When `$version` is empty, propose one from the commits since the newest tag: a breaking change to shipped behavior or any `feat` bumps the minor version, and fixes alone bump the patch version.
The major version stays 0.
Get the operator's agreement on the exact `X.Y.Z` before continuing.

## Step 3: run the live checks

CI runs only the deterministic suite; the checks that spend model calls run here, on all three harnesses.
Confirm the prerequisites first, since a missing one turns into a silent skip rather than a failure:

```sh
command -v claude codex cursor-agent tmux
claude --version; codex --version; cursor-agent --version
ls ~/.claude/.credentials.json ~/.codex/auth.json ~/.config/cursor/auth.json
```

Only proceed when every command succeeded and `cursor-agent` is 2026.08.11 or newer.
Write the three versions into the checklist reply; publish stamps the first two into the publish commit, and the reply is the record for Cursor.
Ask the operator to confirm before starting, since both runs spend model calls and take a while.

```sh
uv run --with pytest python -B -m pytest tests/harness --run-live --keep -s -ra
LLM_WIKI_CURSOR_SMOKE=1 bash tests/run.sh
```

Only proceed when both exit 0 and the output passes both reads.
The pytest short summary lists no `SKIPPED` line other than ones reading `evaluation requires --run-non-deterministic`; any other skip means a harness was not exercised, and an all-skipped run still exits 0.
The bash run prints no `skip  cursor smoke install` line.
Record the `Summary and capture locations:` path pytest prints; the captures are private and stay on this machine.

If a Codex case fails on sandbox initialization, the session ran inside a nested sandbox; rerun with the tool sandbox off rather than changing the harness's own permissions.
Any failing case blocks the release: fix on `src`, push, and restart from step 1.

## Step 4: bump VERSION and preview the notes

```sh
printf '%s\n' "X.Y.Z" > VERSION
git add VERSION
git commit -m "chore(release): bump VERSION to X.Y.Z"
git push origin src
```

Wait for the CI run on that push to report `completed success`, then render the notes:

```sh
git-cliff --unreleased --tag vX.Y.Z --strip all
```

Show the output to the operator and ask two questions.
Is any change a plugin user would notice missing?
Its commit had a type or scope that `cliff.toml` filters out; the operator adds a line for it to the preamble in step 9 rather than rewriting pushed history.
Is anything present that should not be?
Filters live in the `commit_parsers` table of `cliff.toml`; changing them is an ordinary source commit, after which return to the top of this step.

## Step 5: publish

`build/publish.py` records `HEAD` as the source commit but assembles from the working tree, so both must match the pushed `src`.

```sh
git status --porcelain
git rev-parse HEAD origin/src
uv run build/publish.py --branch main --allow-main
```

Only proceed when the first command printed nothing, the second printed two equal commits, and the report ends with `version:    X.Y.Z` and `tag:        vX.Y.Z`.
Record the `old tip:` line from the report; recovery needs it.
Never pass `--skip-gates` or `--force-version`.
For any refusal, see [recovery.md](recovery.md).

## Step 6: verify locally

```sh
uv run build/publish.py --verify main --tag vX.Y.Z --reachable-from src
```

Only proceed when `published:` and `rebuilt:` show the same hash and the output ends with `verify: the published tree reproduces from its source commit`.
On a refusal, take the publish back with the commands in [recovery.md](recovery.md), then diagnose from the message.

## Step 7: push main and the tag

Nothing has left the machine yet, and everything after this point is public.
Ask the operator to confirm the push, showing the new `main` commit and the tag.

```sh
git push --atomic origin main vX.Y.Z
```

If the remote rejects an atomic push, push `main` first and the tag second.

## Step 8: watch the tag run

```sh
gh run list --workflow ci --limit 3
```

Watch the run whose branch column shows `vX.Y.Z` with `gh run watch <id> --exit-status`.
If its verify step reports a `source-ref` mismatch against the tag, the tag arrived before `main`; rerun with `gh run rerun <id>` once `git ls-remote origin main` shows the new commit.
Any other failure means the published tree is not reproducible; see [recovery.md](recovery.md).

## Step 9: create the GitHub release

Ask the operator for two or three sentences on what this release means to someone who installs the plugin.

```sh
git-cliff --latest --strip all > /tmp/notes-X.Y.Z.md
```

Put the operator's sentences, plus any lines requested in step 4, above the generated list in that file.
Show the operator the complete file, and only after they approve:

```sh
gh release create vX.Y.Z --title "X.Y.Z" --notes-file /tmp/notes-X.Y.Z.md
```

## Step 10: confirm delivery

Consumers install from `main`, and Codex refreshes an install only when the manifest version changes.
In a scratch directory, follow the install instructions from the README on `main` for one harness, read the installed plugin manifest, and confirm its `version` field is `X.Y.Z`.
Report the harness checked and the version seen, and tick the last item.

## Additional resources

- For publish refusals, taking back a local publish, and what to do after a bad push, see [recovery.md](recovery.md)
