# Session start

Session start runs once when an agent session opens in a project.
It gives the model the project's wiki as working memory.
It runs on Claude Code, Codex, and Cursor.

## Who it serves

People using a wiki range from those who have never used version control to experienced engineers.
Session start assumes the least technical of them and lets the model adapt upward.

- Session start itself only does things that cannot harm anyone.
- Anything that needs judgment is left to the model, which explains it in terms of the person's notes.
- The person is asked about their notes, never about version control.
- Technical detail is available to anyone who asks the model for it.

## Terms

| Term             | Meaning                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Project          | The repository or folder the person is working in                                                                         |
| Worktree         | A second working copy of the same project, created by the person or by the tooling                                        |
| Attached wiki    | A wiki that has been set up for the project, kept in `.llm-wiki/` at the top of the project with its own separate history |
| Shared copy      | The copy of the wiki that collaborators have in common, when there is one                                                 |
| Unsaved changes  | Edits to wiki pages that have not been recorded in the wiki's history                                                     |
| Unshared changes | Edits recorded in the wiki's history that the shared copy does not have                                                   |

## Flow

### 1. Find the wiki

A project opts in by having an attached wiki.
Without one, session start does nothing: the model receives nothing, nothing on disk changes, and nothing is contacted.
A session started anywhere inside the project behaves exactly as one started at the top of it.

A session started in a worktree uses the project's wiki.
A worktree never has a wiki of its own, and this holds wherever the worktree sits on disk.
Sessions open at the same time, in the project or in its worktrees, all use the one wiki, so each sees the others' unsaved changes.

### 2. Keep the wiki out of the project

The wiki never appears among the project's own changes.

- When the project already keeps the wiki out, nothing is done.
- Otherwise session start arranges it without modifying any file that belongs to the project.
- The arrangement applies only to this person's copy of the project and is never passed on to collaborators.

### 3. Bring the wiki up to date

The update is best effort.
Whatever happens in this step, orientation follows and uses the wiki as it then stands.

| Wiki state                                                  | What happens                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------ |
| There is no shared copy                                     | Nothing; the wiki is complete on its own                     |
| Has unsaved changes                                         | The wiki is left exactly as it is; the model is given a note |
| The shared copy cannot be reached                           | Nothing changes; the wiki is used as it is                   |
| Matches the shared copy                                     | Nothing changes                                              |
| The shared copy is newer, and there are no unshared changes | The wiki is brought up to date with the shared copy          |
| Has unshared changes, and the shared copy has nothing new   | Nothing changes; the model is given a note                   |
| Has unshared changes, and the shared copy is newer          | Nothing changes; the model is given a note                   |

Unsaved changes come first.
Until they are saved, the shared copy is not consulted and no other note is given.

These rules hold in every case:

- Unsaved and unshared changes are never lost or altered.
- Session start itself never sends anything to the shared copy.
- The person is never asked to sign in or enter a password.
- Session start never holds a session indefinitely while waiting for the shared copy.
- A shared copy that does not answer is treated as unreachable.

### 4. Orient the model

The model receives:

- A statement that the project has a wiki, where it is, that it is separate from the project, and how the model is expected to maintain it.
  The location given is usable from wherever the session started, including from a worktree.
- The wiki guidance.
- The wiki's index.
- The last five log entries, or all of them when there are fewer.

The index and log are the wiki's own.
This holds when the project has been renamed since the wiki was set up.
They reflect the wiki after the update step, so a wiki that was brought up to date is presented in its updated state.

## What the model is told

Session start says something beyond orientation only when someone needs to act.

| Situation                                                                                    | Model receives                                               | Person is involved |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------ |
| No attached wiki                                                                             | Nothing                                                      | No                 |
| No shared copy, shared copy unreachable, matches the shared copy, or just brought up to date | Orientation only                                             | No                 |
| Unsaved changes                                                                              | Orientation and a note naming the changed pages              | Yes, asked first   |
| Unshared changes, and the shared copy has nothing new                                        | Orientation and a note naming the pages not yet shared       | Yes, asked first   |
| Unshared changes, and the shared copy is newer                                               | Orientation and a note naming the pages changed on each side | Yes, asked first   |

Every note is an instruction.
It states the situation in plain terms, what the model should do, and whether to ask the person first.

### Unsaved changes

The note names the pages that have unsaved changes, so the model can ask about them without investigating first.
It tells the model to:

- Tell the person, in plain language, that their notes have unsaved changes, and name the pages.
- State no cause, because the changes may come from an earlier session, from the person's own edits, or from another session that is still open.
- Ask whether to save them, and save only after a yes.
- Raise this alongside answering the person's first request, not in place of answering it.

This applies only to changes found at session start.
Edits the model makes itself during the session are saved without asking.

The request is made in every session for as long as the unsaved changes remain, and the wiki is not brought up to date in the meantime.
Session start keeps no record of an earlier answer.

### Unshared changes

This note is given when the wiki has unshared changes, the shared copy can be reached, and the shared copy has nothing new.
It names the pages that have unshared changes.
It tells the model to:

- Tell the person, in plain language, that some of their notes have not yet been shared with their collaborators, and name the pages.
- Ask whether to share them, and share only after a yes.
- Raise this alongside answering the person's first request, not in place of answering it.

The suggestion is made in every session for as long as the unshared changes remain.
Session start keeps no record of an earlier answer.
No suggestion is made when the shared copy cannot be reached.

### Changes on both sides

This note is given when the wiki has unshared changes and the shared copy is newer.
Each then has changes the other lacks, so the wiki cannot simply be brought up to date and its changes cannot simply be shared.
Session start leaves the wiki exactly as it is and never combines the two itself.

The note names the pages that collaborators have changed and the pages that have unshared changes.
It tells the model to:

- Tell the person, in plain language, that their collaborators have added to the wiki and that their own copy also has changes the others have not seen, and name the pages.
- Ask whether to bring the collaborators' changes into their copy, and do so only after a yes.
- Keep both sides' content when combining, never dropping or overwriting either.
- Ask the person, in terms of their notes, wherever both sides changed the same thing and the right result is not clear.
- Raise this alongside answering the person's first request, not in place of answering it.

The request is made in every session for as long as both sides have changes the other lacks, and the wiki receives nothing from the shared copy in the meantime.
Session start keeps no record of an earlier answer.
Once the two are combined, the person's own changes are still unshared, and the suggestion to share applies.

## What the person sees

- Everything that matters is delivered to the model, on every platform.
- Claude Code also shows the person a one-line status giving the wiki's name, page count, and log entry count.
- Nothing is conveyed only through that status line, because Codex and Cursor do not show one.
- Session start never shows an error and never prevents a session from opening.

## Guarantees

These hold for every combination of where the session starts, the state of the wiki, and the state of the shared copy.

1. With no attached wiki, the model receives nothing and nothing on disk changes.
2. No file belonging to the project is ever modified, and the wiki never appears among the project's changes.
3. Unsaved and unshared changes in the wiki survive session start unaltered.
4. Session start itself never modifies the shared copy.
5. Session start never holds a session indefinitely, even when the shared copy never responds.
6. When the shared copy is reachable and the wiki has no unsaved or unshared changes, the model receives the shared copy's index and log.
7. The result is the same from everywhere inside the project and from every worktree of it.
8. Situations that need no action give the model the same thing as one another.
9. Whenever a wiki is attached, orientation is delivered, whatever the outcome of the earlier steps.
10. Session start never shows an error and never prevents a session from opening.

## Open decisions

### A `.llm-wiki/` folder that is not a working wiki

| Option                       | Effect                                       |
| ---------------------------- | -------------------------------------------- |
| Treat it as no attached wiki | Session start does nothing                   |
| Give the model a note        | The model can explain and offer to repair it |

This depends on a larger question: whether a wiki may be kept as part of the project itself instead of separate from it.
In that case a `.llm-wiki/` folder without its own history would be a working wiki, not a broken one.
The same question bears on the definition of an attached wiki and on keeping the wiki out of the project.

### Conditions with no agreed response

Each of these needs one of three responses: handle it quietly, raise it with the person, or say nothing.

| Condition                                                    | Consequence if nothing is done                 |
| ------------------------------------------------------------ | ---------------------------------------------- |
| Something the wiki tooling needs is missing from the machine | Reminders to check wiki edits do not appear    |
| The project is set up to include `.llm-wiki/` in its changes | The wiki appears among the project's changes   |
| The project is not under version control                     | None; there is nothing to keep the wiki out of |
| The index or log is missing                                  | Orientation is incomplete                      |
