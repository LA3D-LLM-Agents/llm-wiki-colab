#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Assemble the artifact tree that becomes the `main` branch.

This script is the single definition of what `main` contains. It runs
identically locally (writing to `build/out/`) and in CI (writing what gets
published).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"

MARKETPLACE_NAME = "llm-wiki-colab"
PLUGIN_NAME = "llm-wiki"
MARKETPLACE_DESCRIPTION = (
    "LLM-wiki durable-memory plugins (Claude Code adapter; more platforms to follow)."
)
PLUGIN_DESCRIPTION = (
    "Opt-in per-repo llm-wiki memory for Claude Code: SessionStart orientation "
    "(index + last-5 log), verification-gate advisory, wiki-write-protocol push, "
    "and a knowledge-graph build."
)
PLUGIN_SOURCE = "./claude/plugins/llm-wiki"

TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")

EXCLUDED_NAMES = {".DS_Store", "__pycache__"}
EXCLUDED_PLUGIN_SUBPATHS = {Path("core/scripts/kg/build")}


class AssembleError(Exception):
    """A fatal, user-facing build failure."""


def git(*args: str) -> str:
    """Run a read-only git command in the repo root and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssembleError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or 'no output'}"
        )
    return result.stdout.strip()


def parse_owner_repo(remote_url: str) -> str:
    """Extract OWNER/REPO from an https or ssh git remote URL."""
    url = remote_url.strip().removesuffix(".git")
    match = re.search(r"[:/]([^/:]+)/([^/]+)$", url)
    if not match:
        raise AssembleError(f"cannot parse OWNER/REPO from remote url: {remote_url!r}")
    return f"{match.group(1)}/{match.group(2)}"


def default_owner_repo() -> str:
    """Derive OWNER/REPO from the origin remote."""
    try:
        remote_url = git("remote", "get-url", "origin")
    except AssembleError as exc:
        raise AssembleError(
            "no git remote 'origin' found; pass --owner-repo OWNER/REPO explicitly"
        ) from exc
    return parse_owner_repo(remote_url)


def resolve_out_dir(raw_out: str | None) -> Path:
    """Resolve and sanity-check the output directory."""
    out = Path(raw_out).resolve() if raw_out else REPO_ROOT / "build" / "out"
    out = out.resolve()
    if out == REPO_ROOT or out in REPO_ROOT.parents:
        raise AssembleError(
            f"refusing to use {out} as --out: it is the repo root or a parent of it"
        )
    return out


def reset_dir(out: Path) -> None:
    """Delete and recreate the output directory."""
    if out.is_symlink() or out.is_file():
        out.unlink()
    elif out.is_dir():
        shutil.rmtree(out)
    out.mkdir(parents=True)


def hydrate(text: str, tokens: dict[str, str], origin: str) -> str:
    """Substitute {{token}} placeholders, failing on any token with no value."""
    unknown = sorted({m.group(1) for m in TOKEN_RE.finditer(text)} - set(tokens))
    if unknown:
        raise AssembleError(
            f"{origin}: unknown template token(s): "
            + ", ".join(f"{{{{{name}}}}}" for name in unknown)
        )
    return TOKEN_RE.sub(lambda m: tokens[m.group(1)], text)


def render_template(name: str, dest: Path, tokens: dict[str, str]) -> None:
    """Hydrate one template from build/templates into the output tree."""
    src = TEMPLATE_DIR / name
    if not src.is_file():
        raise AssembleError(f"missing template: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(hydrate(src.read_text(encoding="utf-8"), tokens, str(src)))


def copy_repo_file(name: str, out: Path) -> None:
    """Copy a repo-root file verbatim into the output tree."""
    src = REPO_ROOT / name
    if not src.is_file():
        raise AssembleError(f"missing repo file: {src}")
    shutil.copy2(src, out / name)


def plugin_ignore(root: Path):
    """Build a shutil.copytree ignore callable for the plugin source tree."""

    def ignore(directory: str, names: list[str]) -> set[str]:
        here = Path(directory).resolve().relative_to(root)
        skipped = {name for name in names if name in EXCLUDED_NAMES}
        for name in names:
            candidate = (here / name) if str(here) != "." else Path(name)
            if candidate in EXCLUDED_PLUGIN_SUBPATHS:
                skipped.add(name)
        return skipped

    return ignore


def copy_plugin(out: Path) -> None:
    """Copy plugins/llm-wiki into the Claude subtree, minus excluded paths."""
    src = (REPO_ROOT / "plugins" / PLUGIN_NAME).resolve()
    if not src.is_dir():
        raise AssembleError(f"missing plugin source: {src}")
    dest = out / "claude" / "plugins" / PLUGIN_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=plugin_ignore(src))


def write_marketplace(out: Path, owner_repo: str) -> None:
    """Generate .claude-plugin/marketplace.json for the Claude subtree."""
    owner = owner_repo.split("/", 1)[0]
    catalog = {
        "name": MARKETPLACE_NAME,
        "owner": {"name": owner, "url": f"https://github.com/{owner}"},
        "metadata": {"description": MARKETPLACE_DESCRIPTION},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": PLUGIN_SOURCE,
                "description": PLUGIN_DESCRIPTION,
            }
        ],
    }
    dest = out / ".claude-plugin" / "marketplace.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(catalog, indent=2) + "\n")


def scan_for_tokens(out: Path) -> list[str]:
    """Report every surviving {{token}} in the emitted tree as 'path: {{token}}'."""
    findings: list[str] = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in sorted({m.group(1) for m in TOKEN_RE.finditer(text)}):
            findings.append(f"{path.relative_to(out)}: {{{{{name}}}}}")
    return findings


def count_files(out: Path) -> int:
    """Count regular files in the emitted tree."""
    return sum(1 for p in out.rglob("*") if p.is_file())


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble the artifact tree published to the main branch."
    )
    parser.add_argument("--out", help="output directory (default: <repo>/build/out)")
    parser.add_argument("--owner-repo", help="OWNER/REPO (default: from origin remote)")
    parser.add_argument("--source-ref", help="source commit SHA (default: git HEAD)")
    return parser.parse_args(argv)


def assemble(out: Path, owner_repo: str, source_ref: str) -> None:
    """Emit the full artifact tree into an already-validated output directory."""
    tokens = {"owner_repo": owner_repo, "source_ref": source_ref}
    reset_dir(out)
    render_template("readme.md", out / "README.md", tokens)
    copy_repo_file("LICENSE", out)
    copy_repo_file("CITATION.cff", out)
    write_marketplace(out, owner_repo)
    copy_plugin(out)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        out = resolve_out_dir(args.out)
        owner_repo = args.owner_repo or default_owner_repo()
        if owner_repo.count("/") != 1 or not all(owner_repo.split("/")):
            raise AssembleError(f"--owner-repo must be OWNER/REPO, got {owner_repo!r}")
        source_ref = args.source_ref or git("rev-parse", "HEAD")
        assemble(out, owner_repo, source_ref)
    except AssembleError as exc:
        print(f"assemble: error: {exc}", file=sys.stderr)
        return 1

    survivors = scan_for_tokens(out)
    if survivors:
        print("assemble: error: unhydrated tokens in output:", file=sys.stderr)
        for finding in survivors:
            print(f"  {finding}", file=sys.stderr)
        return 1

    print(f"out:        {out}")
    print(f"owner_repo: {owner_repo}")
    print(f"source_ref: {source_ref}")
    print(f"files:      {count_files(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
