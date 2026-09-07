#!/usr/bin/env python3
"""update_wiki fast-forward mechanics: clean-FF, dirty gate, divergence, guard.

Exercises the update stage directly against real git (and real jj, when
available). Usage: update_mechanics_test.py <path-to-20-update-wiki.py>

Each check is built to discriminate (observe-the-failure): the happy path
asserts HEAD actually moved from a known-behind state to the upstream tip; the
dirty gate is proved by removing the dirtiness and watching the SAME repo then
advance, so a silently-broken fast-forward would fail the contrast rather than
pass. The jj block covers the case git status must catch but jj would not have
snapshotted: a tracked edit on disk with no jj command run since.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path

hook_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("ensure_wiki", hook_path)
ew = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ew)

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "JJ_CONFIG": os.devnull,
}

results = []
def check(label, cond):
    results.append((label, bool(cond)))


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True)


def jj(*args, cwd=None):
    return subprocess.run(
        ["jj", "--config", "user.name=t", "--config", "user.email=t@t",
         "--config", "ui.color=never", *args],
        cwd=cwd, env=ENV, capture_output=True, text=True,
    )


def head(repo):
    return git("-C", str(repo), "rev-parse", "HEAD").stdout.strip()


def tip(bare, branch="master"):
    return git("-C", str(bare), "rev-parse", branch).stdout.strip()


def make_upstream(base, name):
    """Bare 'master' wiki remote with one commit; return (bare_path, seed_path)."""
    bare = base / f"{name}.git"
    # `git init -b <branch>` was added in git 2.28; on 2.25 (Ubuntu 20.04
    # default, one of the CI matrix entries) the flag is rejected and the bare
    # repo is never created, cascading every later step into FileNotFoundError.
    # `git init --bare` then explicit `symbolic-ref HEAD` is portable to 2.7+
    # and forces the branch name regardless of `init.defaultBranch`.
    git("init", "-q", "--bare", str(bare))
    git("-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/master")
    seed = base / f"{name}.seed"
    git("clone", "-q", str(bare), str(seed))
    (seed / "index.md").write_text("A\n")
    git("-C", str(seed), "add", ".")
    git("-C", str(seed), "commit", "-qm", "A")
    git("-C", str(seed), "push", "-q", "-u", "origin", "master")
    return bare, seed


def advance(seed, bare, tag):
    """Add one commit upstream so a checkout cloned earlier is now behind."""
    (seed / "index.md").write_text(f"A\n{tag}\n")
    git("-C", str(seed), "commit", "-qam", tag)
    git("-C", str(seed), "push", "-q", "origin", "master")


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    # ---- GIT: clean + behind -> fast-forwards to the upstream tip ----
    bare, seed = make_upstream(base, "g_happy")
    wiki = base / "g_happy.wiki"
    git("clone", "-q", str(bare), str(wiki))
    advance(seed, bare, "B")
    check("git happy: precondition — clone is behind upstream", head(wiki) != tip(bare))
    r = ew.update_wiki(wiki)
    check("git happy: reports refreshed memory", "refresh complete" in r)
    check("git happy: HEAD advanced to upstream tip", head(wiki) == tip(bare))

    # ---- GIT: already up to date -> no-op, silent ----
    bare, seed = make_upstream(base, "g_noop")
    wiki = base / "g_noop.wiki"
    git("clone", "-q", str(bare), str(wiki))
    before = head(wiki)
    r = ew.update_wiki(wiki)
    check("git uptodate: reports refreshed memory", "refresh complete" in r)
    check("git uptodate: HEAD unchanged", head(wiki) == before)

    # ---- GIT: dirty (untracked) + behind -> gate blocks the FF ----
    # Contrast: clear the dirtiness and the SAME repo advances, proving the
    # gate (not a broken fast-forward) is what held it back.
    bare, seed = make_upstream(base, "g_dirty")
    wiki = base / "g_dirty.wiki"
    git("clone", "-q", str(bare), str(wiki))
    advance(seed, bare, "B")
    (wiki / "scratch.md").write_text("wip\n")
    before = head(wiki)
    r = ew.update_wiki(wiki)
    check("git dirty: reports preserved local changes", "local changes preserved" in r)
    check("git dirty: HEAD NOT advanced while dirty", head(wiki) == before)
    (wiki / "scratch.md").unlink()
    r2 = ew.update_wiki(wiki)
    check("git dirty: contrast — advances once clean", head(wiki) == tip(bare) and "refresh complete" in r2)

    # ---- GIT: dirty (modified tracked, uncommitted) -> blocked, edit kept ----
    bare, seed = make_upstream(base, "g_edit")
    wiki = base / "g_edit.wiki"
    git("clone", "-q", str(bare), str(wiki))
    advance(seed, bare, "B")
    (wiki / "index.md").write_text("A\nLOCAL\n")
    before = head(wiki)
    r = ew.update_wiki(wiki)
    check("git tracked-edit: reports preserved local changes", "local changes preserved" in r)
    check("git tracked-edit: HEAD NOT advanced", head(wiki) == before)
    check("git tracked-edit: local edit preserved", (wiki / "index.md").read_text() == "A\nLOCAL\n")

    # ---- GIT: ahead + behind (diverged) -> refused with a nudge ----
    bare, seed = make_upstream(base, "g_div")
    wiki = base / "g_div.wiki"
    git("clone", "-q", str(bare), str(wiki))
    (wiki / "local.md").write_text("mine\n")
    git("-C", str(wiki), "add", ".")
    git("-C", str(wiki), "commit", "-qm", "local")
    advance(seed, bare, "B")
    local_head = head(wiki)
    r = ew.update_wiki(wiki)
    check("git diverged: returns a nudge message", bool(r))
    check("git diverged: HEAD not moved to upstream tip", head(wiki) != tip(bare))
    check("git diverged: HEAD still at the local commit", head(wiki) == local_head)

    # Failed network operations must report stale local memory and never merge.
    bare, seed = make_upstream(base, "g_failure")
    wiki = base / "g_failure.wiki"
    git("clone", "-q", str(bare), str(wiki))
    before = head(wiki)
    real_run = subprocess.run
    for operation in ("fetch", "remote"):
        if operation == "remote":
            git("-C", str(wiki), "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        calls = []
        def timed_out(argv, **kwargs):
            calls.append(argv[3:])
            if argv[3:4] == [operation] and (operation != "remote" or argv[4:5] == ["show"]):
                check("network timeout is bounded", kwargs["timeout"] == ew.UPDATE_TIMEOUT_SECONDS)
                check("network is noninteractive", kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
                      and "BatchMode=yes" in kwargs["env"]["GIT_SSH_COMMAND"])
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            return real_run(argv, **kwargs)
        with patch.object(ew.subprocess, "run", side_effect=timed_out):
            result = ew.update_wiki(wiki)
        check(f"{operation} timeout: reports unknown freshness", "Remote freshness is unknown" in result)
        check(f"{operation} timeout: never merges", not any(c[0] == "merge" for c in calls))
        check(f"{operation} timeout: preserves HEAD", head(wiki) == before)

    # ---- GIT: no origin remote -> refuses before any network, HEAD unchanged ----
    # A wiki created locally by /wiki-init but never pushed has no origin. The
    # guard must say so rather than letting `git fetch origin <branch>` fail
    # into the generic "fetch failed" wording, and must not touch the checkout.
    wiki = base / "g_noremote"
    wiki.mkdir()
    git("init", "-q", str(wiki))
    (wiki / "index.md").write_text("A\n")
    git("-C", str(wiki), "add", ".")
    git("-C", str(wiki), "commit", "-qm", "A")
    before = head(wiki)
    calls = []
    def record(argv, **kwargs):
        calls.append(argv[3:])
        return real_run(argv, **kwargs)
    with patch.object(ew.subprocess, "run", side_effect=record):
        r = ew.update_wiki(wiki)
    check("git no-origin: names the missing origin remote",
          bool(r) and "no origin remote configured" in r)
    check("git no-origin: never fetches or merges",
          not any(c[:1] in (["fetch"], ["merge"]) for c in calls))
    check("git no-origin: HEAD unchanged", head(wiki) == before)

    # ---- GIT: wiki dir is NOT its own repo root -> guard bails, parent safe ----
    # The parent is itself a CLEAN clone that is behind its own upstream, with a
    # committed (non-repo) dir at wiki/p.wiki. With the weak --is-inside-work-
    # tree check the wiki dir resolves to the parent, the parent is clean, its
    # origin/HEAD resolves, and update_wiki would fast-forward the PARENT — so
    # this case discriminates only because the parent is clean and advanceable.
    # The --show-toplevel guard must refuse, leaving the parent behind.
    bare, seed = make_upstream(base, "guard")
    # Ignore wiki/ in the upstream (mirrors the real repo's wiki/*.wiki/ ignore)
    # so the nested dir leaves the parent clean. Only seed ever pushes, so bare
    # never diverges and the parent stays a clean fast-forwardable clone.
    (seed / ".gitignore").write_text("/wiki/\n")
    git("-C", str(seed), "add", ".gitignore")
    git("-C", str(seed), "commit", "-qm", "ignore wiki/")
    git("-C", str(seed), "push", "-q", "origin", "master")
    parent = base / "guard_parent"
    git("clone", "-q", str(bare), str(parent))
    fake_wiki = parent / "wiki" / "p.wiki"
    fake_wiki.mkdir(parents=True)
    (fake_wiki / "SCHEMA.md").write_text("x\n")  # ignored -> parent stays clean
    advance(seed, bare, "B")  # parent is now behind its own upstream
    parent_before = head(parent)
    iiwt = git("-C", str(fake_wiki), "rev-parse", "--is-inside-work-tree").stdout.strip()
    top = git("-C", str(fake_wiki), "rev-parse", "--show-toplevel").stdout.strip()
    check("guard: contrast — bare is-inside-work-tree matches the parent", iiwt == "true")
    check("guard: contrast — parent is clean and behind (FF would fire)",
          not git("-C", str(parent), "status", "--porcelain").stdout.strip()
          and parent_before != tip(bare))
    r = ew.update_wiki(fake_wiki)
    check("guard: non-own-repo wiki dir -> returns None", r is None)
    check("guard: parent NOT fast-forwarded (HEAD unchanged, still behind)",
          head(parent) == parent_before and head(parent) != tip(bare))

    # ---- JJ: colocated cases (skipped cleanly when jj is unavailable) ----
    if shutil.which("jj"):
        # Colocated clone: detached HEAD, no origin/HEAD (forces the remote-show
        # branch detection), jj imports the moved ref lazily.
        bare, seed = make_upstream(base, "j_happy")
        wiki = base / "j_happy.wiki"
        jj("git", "clone", "--colocate", str(bare), str(wiki))
        check("jj happy: precondition — colocated clone has no origin/HEAD",
              git("-C", str(wiki), "symbolic-ref", "--quiet",
                  "refs/remotes/origin/HEAD").returncode != 0)
        advance(seed, bare, "B")
        check("jj happy: precondition — clone is behind upstream", head(wiki) != tip(bare))
        r = ew.update_wiki(wiki)
        check("jj happy: reports refreshed memory", "refresh complete" in r)
        check("jj happy: HEAD advanced to upstream tip", head(wiki) == tip(bare))

        # The case git status must catch but jj has NOT snapshotted: a tracked
        # edit written straight to disk with no jj command run since.
        bare, seed = make_upstream(base, "j_edit")
        wiki = base / "j_edit.wiki"
        jj("git", "clone", "--colocate", str(bare), str(wiki))
        advance(seed, bare, "B")
        (wiki / "index.md").write_text("A\nUNSNAPSHOTTED\n")  # no jj command after
        before = head(wiki)
        r = ew.update_wiki(wiki)
        check("jj unsnapshotted-edit: reports preserved local changes", "local changes preserved" in r)
        check("jj unsnapshotted-edit: HEAD NOT advanced", head(wiki) == before)
        check("jj unsnapshotted-edit: on-disk edit preserved",
              (wiki / "index.md").read_text() == "A\nUNSNAPSHOTTED\n")
    else:
        check("jj cases SKIPPED (jj not on PATH)", True)

failed = [l for l, c in results if not c]
for l, c in results:
    print(f"  [{'PASS' if c else 'FAIL'}] {l}", file=sys.stderr)
if failed:
    print("FAILED: " + "; ".join(failed), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
