#!/usr/bin/env python3
"""Refresh an attached wiki before orientation; preserve local work."""

import os
import subprocess
from pathlib import Path
from typing import Optional

# How long any single update network/merge step may take, so session start
# never hangs on the network.
UPDATE_TIMEOUT_SECONDS = 30


def update_wiki(wiki_dir: Path) -> Optional[str]:
    """Fast-forward an already-present wiki checkout to upstream when safe.

    Returns a model-visible refresh outcome, or None for an invalid attachment.
    Dirty worktrees are left untouched before any network operation. Fetch and
    merge are bounded and noninteractive. Fast-forward-only merging preserves
    local commits; colocated jj imports moved Git refs on its next command.
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

    # Leave local work untouched and skip network activity while dirty.
    status = g("status", "--porcelain")
    if status is None:
        return "Wiki refresh failed: unable to inspect local changes; using local memory. Remote freshness is unknown."
    if status.stdout.strip():
        return "Wiki refresh skipped: local changes preserved; using local memory. Remote freshness is unknown."

    # Default branch, detected not guessed (mirrors lw_default_branch in
    # init-wiki.sh). A jj clone does not populate origin/HEAD, so fall
    # back to asking the remote; a non-GitHub or single-branch wiki still
    # resolves to its one branch.
    if g("remote", "get-url", "origin") is None:
        return "Wiki refresh skipped: no origin remote configured; using local memory. Remote freshness is unknown."

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
        return "Wiki refresh failed: unable to determine the remote default branch; using local memory. Remote freshness is unknown."

    # Network, time-bounded and non-interactive so session start never hangs.
    if g("fetch", "origin", branch, timeout=UPDATE_TIMEOUT_SECONDS) is None:
        return "Wiki refresh failed: fetch failed or timed out; using local memory. Remote freshness is unknown."

    upstream = f"origin/{branch}"
    if g("merge", "--ff-only", upstream, timeout=UPDATE_TIMEOUT_SECONDS) is not None:
        # Advanced, or already up to date.
        return "Wiki refresh complete: local memory includes the fetched remote default branch."

    return (
        "Wiki refresh incomplete: fetched upstream but could not fast-forward "
        "the checkout. Local work was preserved; using local memory, which may "
        "be behind upstream. Reconcile with the wiki's own VCS before relying "
        "on its freshness."
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


def run(state):
    ensure_gitignore(state["project_root"])
    message = update_wiki(state["wiki_dir"])
    if message:
        target = "context" if message.startswith("Wiki refresh complete:") else "warnings"
        state[target].append(message)
