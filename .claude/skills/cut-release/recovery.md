# Cut a release: refusals and recovery

Read the section that matches the situation.

## Publish refusals (step 5)

Nothing was published in any of these cases, so `main` and the tags are unchanged.

| Output contains        | Meaning                                                              | Move                                                                                   |
| :--------------------- | :------------------------------------------------------------------- | :------------------------------------------------------------------------------------- |
| `nothing to publish`   | The assembled tree equals `main`'s tip; `VERSION` moved with no source change. | Stop and ask the operator what they intended.                                  |
| `version gate`         | `VERSION` did not increase over what `main` carries.                 | Return to step 4.                                                                      |
| `already names`        | A tag `vX.Y.Z` exists on a different commit.                         | Stop and show the operator; only they can say whether that tag was a mistake.          |
| `gates failed`         | The behavior suite failed against the assembled tree.                | Fix on `src` as ordinary commits, push, and restart from step 1.                       |
| `refusing to publish`  | `--allow-main` was omitted.                                          | Rerun with the flag.                                                                   |

## Taking back a local publish (after step 5, before step 7)

A publish is two local refs.
Restore both with the `old tip:` commit recorded in step 5.

```sh
git update-ref refs/heads/main <old tip>
git tag -d vX.Y.Z
```

Confirm with `git tag --list 'v*'` and `git log -1 main` before doing anything else, then fix the cause on `src` and restart from step 1.

## After a bad push (step 7 onward)

Never move `main` or the tag once pushed.
Codex caches installs by version, so a moved `vX.Y.Z` would leave some installs on a tree nobody can reproduce.
Fix the problem on `src` as ordinary commits, choose the next patch version, and run the whole procedure again from step 1.

## A collaborator sees the tag on a different commit

Their git refused to update an existing local tag on fetch.
They run `git fetch --force --tags`.
