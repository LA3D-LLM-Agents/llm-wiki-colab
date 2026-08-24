#!/usr/bin/env python3
"""SessionStart hook: keep an already-attached wiki current, silently.

Opt-in model: a repo has durable memory only if it has a .llm-wiki/ directory,
created by the user running /wiki-init (which clones or scaffolds it). This hook
is deliberately narrow:

  - .llm-wiki/ present -> fast-forward it to upstream when that is safe, and
    ensure it is gitignored. Silent unless it is behind and cannot be advanced.
  - .llm-wiki/ absent  -> do nothing, silently. This hook NEVER auto-clones or
    prompts. Attaching a repo to a wiki is /wiki-init's job, not the session
    hook's, so a globally-installed plugin stays silent in every repo the user
    has not explicitly opted in, even ones that happen to have a GitHub wiki.

Output contract: at most one JSON object on stdout via the SessionStart
hookSpecificOutput.additionalContext channel; any unexpected condition exits
cleanly with no output.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# How long any single update network/merge step may take, so session start
# never hangs on the network.
UPDATE_TIMEOUT_SECONDS = 30


def git(*args: str) -> Optional[str]:
    """Run a git command, returning stripped stdout or None on any failure."""
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip() or None


def update_wiki(wiki_dir: Path) -> Optional[str]:
    """Fast-forward an already-present wiki checkout to upstream when safe.

    Returns None when the hook should stay silent (advanced, already current,
    not git-backed, or the user has local changes to leave alone). Returns a
    short message when the wiki is behind but cannot be fast-forwarded
    (unpushed local commits or divergence the user must resolve).

    Safety rests on two independent git-level guards, both verified against a
    colocated jj wiki. A clean `git status --porcelain` reads the working tree
    off disk, so it catches edits jj has not snapshotted into @ (jj only
    snapshots when a jj command runs in the wiki, which this hook never does),
    and a committed-but-unpushed change reads as clean here but is caught by
    --ff-only below. `merge --ff-only` advances on a true fast-forward and
    refuses an ahead or diverged checkout. For a colocated jj wiki the moved
    ref is imported by jj on its next command; a plain-git wiki advances its
    branch directly. A Sapling/hg wiki has no working .git and bails at the
    first command.
    """
    env = {
        **os.environ,
        # Never block on a terminal/SSH credential prompt at session start.
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
    }

    def g(*args: str, timeout: Optional[int] = None):
        try:
            return subprocess.run(
                ["git", "-C", str(wiki_dir), *args],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=timeout,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

    # The wiki must be its OWN git repo root (plain git, or jj colocated). A
    # bare --is-inside-work-tree would walk up and match the main repo when the
    # wiki dir is not itself a checkout, so fetch/merge could then operate on
    # the wrong repository; comparing the toplevel rules that out.
    top = g("rev-parse", "--show-toplevel")
    if top is None or Path(top.stdout.strip()).resolve() != wiki_dir.resolve():
        return None

    # Any local change -> early out, before any network. Leaves in-progress
    # work untouched and avoids a session-start nudge while the user is mid-edit.
    status = g("status", "--porcelain")
    if status is None:
        return None
    if status.stdout.strip():
        return None

    # Default branch, detected not guessed (mirrors lw_default_branch in
    # scripts/lib/git.sh). A jj clone does not populate origin/HEAD, so fall
    # back to asking the remote; a non-GitHub or single-branch wiki still
    # resolves to its one branch.
    branch = None
    sref = g("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if sref and sref.stdout.strip():
        branch = sref.stdout.strip().split("/", 1)[-1]
    else:
        show = g("remote", "show", "origin", timeout=UPDATE_TIMEOUT_SECONDS)
        if show:
            for line in show.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("HEAD branch:"):
                    branch = stripped.split(":", 1)[1].strip()
                    break
    if not branch or branch == "(unknown)":
        return None

    # Network, time-bounded and non-interactive so session start never hangs.
    if g("fetch", "origin", branch, timeout=UPDATE_TIMEOUT_SECONDS) is None:
        return None

    upstream = f"origin/{branch}"
    if g("merge", "--ff-only", upstream, timeout=UPDATE_TIMEOUT_SECONDS) is not None:
        # Advanced, or already up to date.
        return None

    # Behind but not fast-forwardable: unpushed local commits or divergence.
    return (
        f"The wiki at {wiki_dir.name}/ is behind upstream but could not be "
        f"fast-forwarded (unpushed local commits or divergence). Reconcile it "
        f"with the wiki's own VCS before relying on its memory."
    )


def emit(message: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            }
        },
        sys.stdout,
    )


def ensure_gitignore(repo_root: Path) -> None:
    """Ensure the project .gitignore ignores the .llm-wiki/ memory dir.

    The memory is a separate checkout inside the project tree and must not be
    tracked by the main repo. init-wiki.sh adds this line on /wiki-init; this
    keeps it present for an already-attached wiki. Idempotent and best-effort
    (never fails the hook).
    """
    gi = repo_root / ".gitignore"
    line = ".llm-wiki/"
    try:
        content = gi.read_text() if gi.exists() else ""
        if line not in content.splitlines():
            sep = "" if content == "" or content.endswith("\n") else "\n"
            gi.write_text(content + sep + line + "\n")
    except OSError:
        pass


def main() -> int:
    # Resolve the repo root; bail quietly if we are not in a working tree.
    root = git("rev-parse", "--show-toplevel")
    if not root:
        return 0
    repo_root = Path(root)

    wiki_dir = repo_root / ".llm-wiki"
    # Opt-in by presence: no .llm-wiki/ means this repo has not been attached to a
    # wiki, so stay silent and do NOT auto-clone from the remote (even if the repo
    # has a GitHub wiki). Attaching is /wiki-init's job; the session hook only
    # maintains an existing checkout.
    if not wiki_dir.is_dir():
        return 0

    ensure_gitignore(repo_root)
    message = update_wiki(wiki_dir)
    if message:
        emit(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
