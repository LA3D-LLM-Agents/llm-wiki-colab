#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Publish an assembled artifact tree onto a branch, locally.

The script assembles the artifact tree into a scratch directory, runs the
behavior suite against that tree, and appends exactly one commit of pure build
output to the target branch using a temporary index. A publish to main also
tags the source commit with the version it shipped. The working copy is never
touched and nothing is pushed; pushing is the caller's job.

--verify REF rebuilds the artifact from the source commit a publish commit
records and refuses unless the tree hashes match, so a second machine can
prove a published tree is exactly what its source says it is.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ASSEMBLE = SCRIPT_DIR / "assemble.py"
TEST_RUNNER = REPO_ROOT / "tests" / "run.sh"

BOOTSTRAP_BRANCH = "main"
NULL_OID = "0" * 40
TAG_PREFIX = "v"

# Where a published tree states its version. VERSION_PATH is what every tree
# built after the VERSION file landed carries; the legacy paths are the emitted
# Claude manifest locations of earlier layouts, newest first. The adapters path
# is the pre-restructure layout that today's main still carries; without it the
# first gated publish onto main would take the bootstrap waiver and check
# nothing.
VERSION_PATH = "VERSION"
LEGACY_VERSION_PATHS = (
    "claude/plugins/llm-wiki/.claude-plugin/plugin.json",
    "adapters/claude-code/.claude-plugin/plugin.json",
)
# (0|[1-9]\d*) rather than \d+: semver forbids leading zeros, and Codex uses
# the string as a cache directory name, so 01.2.3 would be a distinct cache
# entry the gate then reads back as a confusing previous version.
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TRAILER_RE = re.compile(r"^([a-z][a-z-]*): (.+)$")
OWNER_REPO_RE = re.compile(r"[:/]([^/:]+)/([^/]+)$")

# Ambient git redirection (GIT_DIR and friends, exported by git hooks, bisect
# run, and some CI wrappers) would point every plumbing call here at a
# repository this script was never asked to touch; scrub it so REPO_ROOT and
# the explicit --git-dir are the only repos git can see.
GIT_ENV_SCRUB = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
)


def base_git_env() -> dict[str, str]:
    """os.environ minus the ambient git redirection variables."""
    return {k: v for k, v in os.environ.items() if k not in GIT_ENV_SCRUB}


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
        env=env if env is not None else base_git_env(),
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


def run_assemble(
    out: Path,
    source_ref: str,
    assemble: Path = ASSEMBLE,
    owner_repo: str | None = None,
) -> int:
    """Assemble the artifact tree and return the emitted file count."""
    print(f"===== assemble ({out}) =====", flush=True)
    command = ["uv", "run", str(assemble), "--out", str(out), "--source-ref", source_ref]
    if owner_repo:
        command += ["--owner-repo", owner_repo]
    result = subprocess.run(
        command,
        cwd=str(assemble.parent.parent),
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
    env = dict(base_git_env(), LLM_WIKI_BUILT_TREE=str(gate_tree))
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
        env = dict(base_git_env(), GIT_INDEX_FILE=str(Path(index_dir) / "index"))
        common = [
            f"--git-dir={REPO_ROOT / '.git'}",
            f"--work-tree={out}",
        ]
        git(*common, "add", "-A", "--force", ".", env=env, cwd=out)
        return git(*common, "write-tree", env=env, cwd=out)


def build_message(
    source_ref: str, file_count: int, version: str, gates_ran: bool
) -> str:
    """Compose the publish commit message.

    Every line after the subject is a trailer that --verify reads back, so the
    commit says for itself whether the suite ran.
    """
    short = source_ref[:12]
    return "\n".join(
        [
            f"build: publish {version} from src {short}",
            "",
            f"version: {version}",
            f"source-ref: {source_ref}",
            f"gates: {'ran' if gates_ran else 'skipped'}",
            f"claude-cli: {tool_version(['claude', '--version'])}",
            f"codex-cli: {tool_version(['codex', '--version'])}",
            f"assembled-files: {file_count}",
            "",
        ]
    )


def parse_trailers(message: str) -> dict[str, str]:
    """Read the key: value lines out of a publish commit message."""
    trailers: dict[str, str] = {}
    for line in message.splitlines():
        match = TRAILER_RE.match(line.strip())
        if match:
            trailers.setdefault(match.group(1), match.group(2).strip())
    return trailers


def cas_ref(ref: str, new_commit: str, expected: str) -> None:
    """Compare-and-swap a ref, failing loudly if it moved underneath us."""
    result = subprocess.run(
        ["git", "update-ref", ref, new_commit, expected],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=base_git_env(),
    )
    if result.returncode != 0:
        raise PublishError(
            f"update-ref {ref} refused (expected old value "
            f"{expected}): {result.stderr.strip() or 'no output'}"
        )


def update_ref(branch: str, new_commit: str, old_commit: str | None) -> None:
    """Move a branch to the new commit, refusing if its tip changed meanwhile."""
    cas_ref(f"refs/heads/{branch}", new_commit, old_commit or NULL_OID)


def release_tag(version: str) -> str:
    return f"{TAG_PREFIX}{version}"


def check_release_tag(version: str, source_ref: str) -> str | None:
    """Refuse when the release tag already names a different source commit.

    Returns the existing tag object so the transaction can verify it has not
    changed, preserving annotated tags as well as lightweight tags.
    """
    tag = release_tag(version)
    existing = git_optional("rev-parse", "--verify", f"refs/tags/{tag}")
    if existing is not None and resolve_ref(f"refs/tags/{tag}") != source_ref:
        raise PublishError(
            f"tag {tag} already names {existing[:12]}, not source {source_ref[:12]}; "
            "a version publishes from one source commit, so bump VERSION or "
            "delete the stale tag"
        )
    return existing


def update_release_refs(
    new_commit: str, old_commit: str | None, version: str,
    source_ref: str, existing_tag: str | None,
) -> str:
    """Move main and create or verify its source tag in one transaction."""
    tag = release_tag(version)
    tag_command = (
        f"verify refs/tags/{tag} {existing_tag}"
        if existing_tag else f"create refs/tags/{tag} {source_ref}"
    )
    result = subprocess.run(
        ["git", "update-ref", "--stdin"],
        input=(
            "start\n"
            f"update refs/heads/{BOOTSTRAP_BRANCH} {new_commit} {old_commit or NULL_OID}\n"
            f"{tag_command}\nprepare\ncommit\n"
        ),
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
        env=base_git_env(),
    )
    if result.returncode != 0:
        raise PublishError(
            f"release ref transaction refused; nothing published: {result.stderr.strip() or 'no output'}"
        )
    return tag


def default_owner_repo() -> str:
    """OWNER/REPO from the origin remote, for an assemble run outside the repo."""
    url = git_optional("remote", "get-url", "origin")
    if not url:
        raise PublishError(
            "no git remote 'origin'; pass --owner-repo OWNER/REPO explicitly"
        )
    match = OWNER_REPO_RE.search(url.strip().removesuffix(".git"))
    if not match:
        raise PublishError(f"cannot parse OWNER/REPO from remote url: {url!r}")
    return f"{match.group(1)}/{match.group(2)}"


def extract_source(commit: str, dest: Path) -> None:
    """Materialize a commit's tree at dest, exactly as committed.

    The working copy is never used: a publish made with uncommitted edits is
    one of the things --verify exists to catch.
    """
    result = subprocess.run(
        ["git", "archive", "--format=tar", commit],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=False,
        env=base_git_env(),
    )
    if result.returncode != 0:
        raise PublishError(
            f"git archive {commit[:12]} failed: "
            f"{result.stderr.decode(errors='replace').strip() or 'no output'}"
        )
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        archive.extractall(dest, filter="data")


def parse_semver(text: str, origin: str) -> tuple[int, int, int]:
    """Parse MAJOR.MINOR.PATCH into a comparable tuple."""
    match = SEMVER_RE.match(text.strip())
    if not match:
        raise PublishError(
            f"{origin}: not a MAJOR.MINOR.PATCH version: {text.strip()!r}"
        )
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def tree_version(out: Path) -> str:
    """Read the version the freshly assembled tree carries."""
    path = out / VERSION_PATH
    try:
        version = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PublishError(f"assembled tree has no {VERSION_PATH}: {exc}") from exc
    parse_semver(version, f"assembled {VERSION_PATH}")
    return version


def parent_version(parent: str) -> tuple[str, str] | None:
    """Return (version, path) as recorded in a commit's tree, or None."""
    raw = git_optional("show", f"{parent}:{VERSION_PATH}")
    if raw:
        return raw.strip(), VERSION_PATH
    for legacy in LEGACY_VERSION_PATHS:
        blob = git_optional("show", f"{parent}:{legacy}")
        if not blob:
            continue
        try:
            value = json.loads(blob).get("version")
        except json.JSONDecodeError:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip(), legacy
    return None


def enforce_version_gate(
    branch: str, parent: str | None, version: str, forced: bool
) -> None:
    """Refuse to publish a changed tree that reuses the parent's version.

    Only reached once the assembled tree is known to differ from the parent's,
    so a publish is genuinely happening. Codex refreshes an install only when
    the manifest version changes, so republishing a changed tree under an
    unchanged version ships an update Codex users never receive.
    """
    if forced:
        print(
            "publish: WARNING: --force-version set; the version gate did NOT run. "
            f"Branch {branch} may now carry a tree that no version bump announces.",
            file=sys.stderr,
            flush=True,
        )
        return
    if parent is None:
        print(
            f"publish: bootstrap: root commit, no parent version to compare ({version})"
        )
        return
    found = parent_version(parent)
    if found is None:
        searched = ", ".join((VERSION_PATH, *LEGACY_VERSION_PATHS))
        print(
            f"publish: bootstrap: parent {parent[:12]} records no version at "
            f"any of {searched}; gate not applied ({version})"
        )
        return
    previous, origin = found
    new = parse_semver(version, f"assembled {VERSION_PATH}")
    old = parse_semver(previous, f"{parent[:12]}:{origin}")
    if new > old:
        return
    verb = "is unchanged from" if new == old else "is lower than"
    raise PublishError(
        f"version gate: the assembled tree differs from refs/heads/{branch}, but "
        f"VERSION {version} {verb} the {previous} recorded at {parent[:12]}:{origin}.\n"
        "  Bump VERSION and publish again. Codex refreshes an install only when the\n"
        "  manifest version changes, so a changed tree under an unchanged version\n"
        "  reaches no Codex user.\n"
        "  --force-version overrides this on a throwaway branch; it is refused for "
        f"{BOOTSTRAP_BRANCH}."
    )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble, gate, and append one build commit to a branch."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--branch", help="target branch name")
    mode.add_argument(
        "--verify",
        metavar="REF",
        help=(
            "rebuild the artifact from the source commit REF's tip records and "
            "refuse unless the trees match; publishes nothing"
        ),
    )
    parser.add_argument("--source-ref", help="source commit SHA (default: git HEAD)")
    parser.add_argument(
        "--allow-main",
        action="store_true",
        help=f"permit publishing to {BOOTSTRAP_BRANCH}",
    )
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        help="skip the behavior suite (plumbing tests only); the version gate still runs",
    )
    parser.add_argument(
        "--force-version",
        action="store_true",
        help=(
            "publish a changed tree without a VERSION bump; "
            f"refused for {BOOTSTRAP_BRANCH}"
        ),
    )
    verify = parser.add_argument_group("verify options")
    verify.add_argument(
        "--tag",
        help="release tag that must name the recorded source commit and its VERSION",
    )
    verify.add_argument(
        "--reachable-from",
        metavar="REF",
        help="the recorded source commit must be an ancestor of REF",
    )
    verify.add_argument(
        "--owner-repo",
        help="OWNER/REPO stamped into the rebuilt tree (default: from origin)",
    )
    verify.add_argument(
        "--allow-skipped-gates",
        action="store_true",
        help="accept a publish whose suite did not run (plumbing tests only)",
    )
    return parser.parse_args(argv)


def publish(args: argparse.Namespace) -> int:
    branch = args.branch
    if branch == BOOTSTRAP_BRANCH and not args.allow_main:
        raise PublishError(
            f"refusing to publish to {BOOTSTRAP_BRANCH} without --allow-main"
        )
    # Checked before anything is assembled: the override exists for throwaway
    # branches, and main must never carry a tree no version bump announces.
    if branch == BOOTSTRAP_BRANCH and args.force_version:
        raise PublishError(
            f"--force-version is refused for {BOOTSTRAP_BRANCH}; bump VERSION instead"
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
        version = tree_version(out)
        # The tree hash and the version gate are both cheap and both decide
        # whether a publish happens at all, so they run before the suite. A
        # contributor who forgot to bump learns in a second rather than after a
        # full gate run, and an unchanged tree costs nothing.
        tree = write_tree(out)
        parent_tree = git("rev-parse", f"{parent}^{{tree}}") if parent else None
        if tree == parent_tree:
            print("nothing to publish")
            return 0
        enforce_version_gate(branch, parent, version, args.force_version)
        # Tags are minted for main only, and the conflict is checked before the
        # suite runs so a stale tag costs seconds rather than a full gate run.
        existing_tag = None
        if branch == BOOTSTRAP_BRANCH:
            existing_tag = check_release_tag(version, source_ref)
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
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    commit_args = ["commit-tree", tree]
    if parent:
        commit_args += ["-p", parent]
    new_commit = git(
        *commit_args,
        "-m",
        build_message(source_ref, file_count, version, not args.skip_gates),
    )
    tag = None
    if branch == BOOTSTRAP_BRANCH:
        tag = update_release_refs(new_commit, branch_tip, version, source_ref, existing_tag)
    else:
        update_ref(branch, new_commit, branch_tip)

    print("")
    print(f"branch:     {branch}")
    print(f"old tip:    {branch_tip or '(none)'}")
    print(f"new commit: {new_commit}")
    print(f"tree:       {tree}")
    print(f"parent:     {parent or '(root commit)'}")
    print(f"source ref: {source_ref}")
    print(f"version:    {version}")
    print(f"tag:        {tag or '(none)'}")
    return 0


def verify(args: argparse.Namespace) -> int:
    """Rebuild REF's tip from the source commit it records and compare trees."""
    tip = resolve_ref(args.verify)
    if tip is None:
        raise PublishError(f"cannot resolve --verify {args.verify!r}")
    trailers = parse_trailers(git("log", "-1", "--format=%B", tip))
    source = trailers.get("source-ref")
    if not source:
        raise PublishError(
            f"{args.verify} ({tip[:12]}) records no source-ref; not a publish commit"
        )
    found = parent_version(tip)
    if found is None:
        raise PublishError(f"{args.verify} ({tip[:12]}) records no version")
    version, _ = found

    gates = trailers.get("gates")
    if gates == "skipped" and not args.allow_skipped_gates:
        raise PublishError(
            f"{args.verify} ({tip[:12]}) was published with --skip-gates; "
            "the behavior suite never ran against this tree"
        )
    if gates is None:
        print(f"verify: note: {tip[:12]} predates the gates trailer; suite status unknown")

    source_commit = resolve_ref(source)
    if source_commit is None:
        raise PublishError(
            f"source commit {source[:12]} is not in this repository; "
            "fetch the full history of the source branch"
        )

    if args.tag:
        if not args.tag.startswith(TAG_PREFIX):
            raise PublishError(f"--tag {args.tag!r} does not start with {TAG_PREFIX!r}")
        tag_commit = resolve_ref(f"refs/tags/{args.tag}")
        if tag_commit is None:
            raise PublishError(f"tag {args.tag} does not exist")
        if tag_commit != source_commit:
            raise PublishError(
                f"tag {args.tag} names {tag_commit[:12]}, but {args.verify} was "
                f"published from {source_commit[:12]}"
            )
        expected = args.tag[len(TAG_PREFIX):]
        if expected != version:
            raise PublishError(
                f"tag {args.tag} says {expected}, but {args.verify} carries VERSION {version}"
            )

    if args.reachable_from:
        base = resolve_ref(args.reachable_from)
        if base is None:
            raise PublishError(f"cannot resolve --reachable-from {args.reachable_from!r}")
        if git_optional("merge-base", "--is-ancestor", source_commit, base) is None:
            raise PublishError(
                f"source commit {source_commit[:12]} is not an ancestor of "
                f"{args.reachable_from} ({base[:12]}); it was rewritten or never pushed"
            )

    owner_repo = args.owner_repo or default_owner_repo()
    workdir = Path(tempfile.mkdtemp(prefix="llm-wiki-verify-"))
    try:
        src = workdir / "src"
        extract_source(source_commit, src)
        assemble = src / "build" / "assemble.py"
        if not assemble.is_file():
            raise PublishError(f"source commit {source_commit[:12]} has no build/assemble.py")
        out = workdir / "tree"
        run_assemble(out, source_commit, assemble=assemble, owner_repo=owner_repo)
        tree = write_tree(out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    tip_tree = git("rev-parse", f"{tip}^{{tree}}")
    print("")
    print(f"ref:        {args.verify} ({tip[:12]})")
    print(f"source ref: {source_commit}")
    print(f"version:    {version}")
    print(f"gates:      {gates or 'unknown'}")
    print(f"published:  {tip_tree}")
    print(f"rebuilt:    {tree}")
    if tree != tip_tree:
        changed = git("diff-tree", "-r", "--name-status", tip_tree, tree)
        raise PublishError(
            f"rebuilt tree {tree[:12]} differs from published tree {tip_tree[:12]}:\n"
            + "\n".join(f"  {line}" for line in changed.splitlines())
        )
    print("verify: the published tree reproduces from its source commit")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        if args.verify:
            return verify(args)
        return publish(args)
    except PublishError as exc:
        print(f"publish: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
