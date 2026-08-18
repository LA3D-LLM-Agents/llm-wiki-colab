#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Publish an assembled artifact tree onto a branch, locally.

The script assembles the artifact tree into a scratch directory, runs the
behavior suite against that tree, and appends exactly one commit of pure build
output to the target branch using a temporary index. The working copy is never
touched and nothing is pushed; pushing is the caller's job.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ASSEMBLE = SCRIPT_DIR / "assemble.py"
TEST_RUNNER = REPO_ROOT / "tests" / "run.sh"

BOOTSTRAP_BRANCH = "main"
NULL_OID = "0" * 40


class PublishError(Exception):
    """A fatal, user-facing publish failure."""


def git(*args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> str:
    """Run a git command and return stdout, raising on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise PublishError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or 'no output'}"
        )
    return result.stdout.strip()


def git_optional(*args: str) -> str | None:
    """Run a git command, returning stdout or None when it fails."""
    try:
        return git(*args)
    except PublishError:
        return None


def resolve_ref(ref: str) -> str | None:
    """Resolve a ref to a full commit SHA, or None if it does not exist."""
    return git_optional("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def tool_version(command: list[str]) -> str:
    """Report a tool's version string, or a placeholder when it is unavailable."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except OSError:
        return "unavailable"
    if result.returncode != 0:
        return "unavailable"
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"


def run_assemble(out: Path, source_ref: str) -> int:
    """Assemble the artifact tree and return the emitted file count."""
    print(f"===== assemble ({out}) =====", flush=True)
    result = subprocess.run(
        ["uv", "run", str(ASSEMBLE), "--out", str(out), "--source-ref", source_ref],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.stdout.flush()
    if result.returncode != 0:
        raise PublishError("assemble failed; nothing published")
    for line in result.stdout.splitlines():
        if line.startswith("files:"):
            return int(line.split(":", 1)[1].strip())
    raise PublishError("assemble produced no file count; nothing published")


def run_gates(out: Path, workdir: Path) -> None:
    """Run the behavior suite against a throwaway copy of the assembled tree.

    The suite writes into the tree it is pointed at (Python bytecode caches, for
    one), so it never sees the tree that gets committed.
    """
    print("===== gates =====", flush=True)
    gate_tree = workdir / "gate"
    shutil.copytree(out, gate_tree)
    marker = gate_tree / ".prebuilt"
    marker.touch()
    env = dict(os.environ, LLM_WIKI_BUILT_TREE=str(gate_tree))
    try:
        result = subprocess.run(
            ["bash", str(TEST_RUNNER)],
            cwd=str(REPO_ROOT),
            env=env,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    finally:
        marker.unlink(missing_ok=True)
        shutil.rmtree(gate_tree, ignore_errors=True)
    if result.returncode != 0:
        raise PublishError(
            f"gates failed (tests/run.sh exit {result.returncode}); nothing published"
        )


def write_tree(out: Path) -> str:
    """Stage the assembled tree in a temporary index and write it as a tree object."""
    with tempfile.TemporaryDirectory(prefix="llm-wiki-index-") as index_dir:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(index_dir) / "index"))
        common = [
            f"--git-dir={REPO_ROOT / '.git'}",
            f"--work-tree={out}",
        ]
        git(*common, "add", "-A", "--force", ".", env=env, cwd=out)
        return git(*common, "write-tree", env=env, cwd=out)


def build_message(source_ref: str, file_count: int) -> str:
    """Compose the publish commit message."""
    short = source_ref[:12]
    return "\n".join(
        [
            f"build: publish from src {short}",
            "",
            f"source-ref: {source_ref}",
            f"claude-cli: {tool_version(['claude', '--version'])}",
            f"assembled-files: {file_count}",
            "",
        ]
    )


def update_ref(branch: str, new_commit: str, old_commit: str | None) -> None:
    """Compare-and-swap the branch ref, failing loudly if it moved underneath us."""
    ref = f"refs/heads/{branch}"
    expected = old_commit if old_commit else NULL_OID
    result = subprocess.run(
        ["git", "update-ref", ref, new_commit, expected],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PublishError(
            f"update-ref {ref} refused (expected old value "
            f"{expected}): {result.stderr.strip() or 'no output'}"
        )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble, gate, and append one build commit to a branch."
    )
    parser.add_argument("--branch", required=True, help="target branch name")
    parser.add_argument("--source-ref", help="source commit SHA (default: git HEAD)")
    parser.add_argument(
        "--allow-main",
        action="store_true",
        help=f"permit publishing to {BOOTSTRAP_BRANCH}",
    )
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        help="skip the behavior suite (plumbing tests only)",
    )
    return parser.parse_args(argv)


def publish(args: argparse.Namespace) -> int:
    branch = args.branch
    if branch == BOOTSTRAP_BRANCH and not args.allow_main:
        raise PublishError(
            f"refusing to publish to {BOOTSTRAP_BRANCH} without --allow-main"
        )

    source_ref = resolve_ref(args.source_ref or "HEAD")
    if source_ref is None:
        raise PublishError(f"cannot resolve --source-ref {args.source_ref or 'HEAD'!r}")

    branch_tip = resolve_ref(f"refs/heads/{branch}")
    parent = branch_tip or resolve_ref(f"refs/heads/{BOOTSTRAP_BRANCH}")
    if branch_tip is None and parent is None:
        raise PublishError(
            f"neither refs/heads/{branch} nor refs/heads/{BOOTSTRAP_BRANCH} exists"
        )

    workdir = Path(tempfile.mkdtemp(prefix="llm-wiki-publish-"))
    out = workdir / "tree"
    try:
        file_count = run_assemble(out, source_ref)
        if args.skip_gates:
            print(
                "publish: WARNING: --skip-gates set; the behavior suite did NOT run. "
                "This is for plumbing tests only and must never be used for a real "
                "publish.",
                file=sys.stderr,
                flush=True,
            )
        else:
            run_gates(out, workdir)
        tree = write_tree(out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    parent_tree = git("rev-parse", f"{parent}^{{tree}}") if parent else None
    if tree == parent_tree:
        print("nothing to publish")
        return 0

    commit_args = ["commit-tree", tree]
    if parent:
        commit_args += ["-p", parent]
    new_commit = git(*commit_args, "-m", build_message(source_ref, file_count))
    update_ref(branch, new_commit, branch_tip)

    print("")
    print(f"branch:     {branch}")
    print(f"old tip:    {branch_tip or '(none)'}")
    print(f"new commit: {new_commit}")
    print(f"tree:       {tree}")
    print(f"parent:     {parent or '(root commit)'}")
    print(f"source ref: {source_ref}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return publish(parse_args(argv))
    except PublishError as exc:
        print(f"publish: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
