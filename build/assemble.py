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
CODEX_PLUGIN_SOURCE = "./codex/plugins/llm-wiki"
CODEX_MARKETPLACE_DISPLAY_NAME = "LLM-wiki Colab"
CODEX_PLUGIN_DESCRIPTION = (
    "Opt-in per-repo llm-wiki memory for Codex: SessionStart orientation "
    "(index + last-5 log), verification-gate advisory, wiki-write-protocol push, "
    "and a knowledge-graph build."
)
CLAUDE_PLUGIN_MANIFEST = Path("plugins/llm-wiki/.claude-plugin/plugin.json")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")

EXCLUDED_NAMES = {".DS_Store", "__pycache__"}
EXCLUDED_PLUGIN_SUBPATHS = {Path("core/scripts/kg/build")}

# Skill frontmatter routing. `name` and `description` are the three-way lowest
# common denominator every harness reads. Everything else belongs to exactly one
# harness, and each emitter drops the keys its harness does not own.
UNIVERSAL_SKILL_KEYS = {"name", "description"}
CLAUDE_ONLY_SKILL_KEYS = {
    "disable-model-invocation",
    "user-invocable",
    "when_to_use",
    "argument-hint",
    "allowed-tools",
    "paths",
    "context",
    "agent",
    "effort",
    "shell",
    "model",
    "hooks",
}
# `metadata` must carry a mapping value: codex silently drops a skill whose
# metadata is a scalar from the model-visible prompt (probed, codex-cli 0.147.0).
CODEX_ONLY_SKILL_KEYS = {"metadata"}

CLAUDE_SKILL_KEYS = UNIVERSAL_SKILL_KEYS | CLAUDE_ONLY_SKILL_KEYS
CODEX_SKILL_KEYS = UNIVERSAL_SKILL_KEYS | CODEX_ONLY_SKILL_KEYS
KNOWN_SKILL_KEYS = CLAUDE_SKILL_KEYS | CODEX_SKILL_KEYS

FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):")


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


def jj(*args: str) -> str:
    """Run a read-only jj command in the repo root and return stdout."""
    result = subprocess.run(
        ["jj", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssembleError(
            f"jj {' '.join(args)} failed: {result.stderr.strip() or 'no output'}"
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
    """Derive OWNER/REPO from the origin remote, via git or jj.

    A secondary jj workspace carries only a .jj pointer and no .git, so git
    fails outright there; jj answers the same question from the shared repo.
    """
    try:
        return parse_owner_repo(git("remote", "get-url", "origin"))
    except (AssembleError, OSError):
        pass
    try:
        for line in jj("git", "remote", "list").splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[0] == "origin":
                return parse_owner_repo(fields[1])
    except (AssembleError, OSError):
        pass
    raise AssembleError(
        "no git remote 'origin' found via git or jj; "
        "pass --owner-repo OWNER/REPO explicitly"
    )


def default_source_ref() -> str:
    """Resolve the current commit, via git or jj."""
    try:
        return git("rev-parse", "HEAD")
    except (AssembleError, OSError):
        pass
    try:
        return jj("log", "-r", "@", "--no-graph", "-T", "commit_id")
    except (AssembleError, OSError):
        pass
    raise AssembleError(
        "cannot resolve HEAD via git or jj; pass --source-ref SHA explicitly"
    )


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


def rewrite_skill_frontmatter(path: Path, allowed: set[str]) -> None:
    """Drop the frontmatter keys this harness does not read, in place.

    The plugin's frontmatter is flat `key: value` YAML, so a line scanner is
    enough and keeps assemble.py dependency-free. An unrecognized key is a hard
    error: a new key must be routed to a harness deliberately, not leak into
    every subtree by default.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise AssembleError(f"{path}: SKILL.md does not open with a --- fence")
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise AssembleError(f"{path}: SKILL.md frontmatter is not closed") from None

    kept: list[str] = []
    keeping = True
    seen: set[str] = set()
    for line in lines[1:close]:
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            key = match.group(1)
            if key not in KNOWN_SKILL_KEYS:
                raise AssembleError(
                    f"{path}: unknown skill frontmatter key {key!r}; add it to "
                    "CLAUDE_ONLY_SKILL_KEYS or CODEX_ONLY_SKILL_KEYS"
                )
            seen.add(key)
            keeping = key in allowed
        # A continuation line (indented, or a list item) belongs to the key above it.
        if keeping:
            kept.append(line)

    missing = sorted(UNIVERSAL_SKILL_KEYS - seen)
    if missing:
        raise AssembleError(
            f"{path}: SKILL.md frontmatter is missing " + ", ".join(missing)
        )

    path.write_text("\n".join(["---", *kept, *lines[close:]]), encoding="utf-8")


def strip_skill_frontmatter(plugin_dir: Path, allowed: set[str]) -> None:
    """Apply the frontmatter routing to every SKILL.md under a plugin subtree."""
    for skill in sorted(plugin_dir.glob("skills/*/SKILL.md")):
        rewrite_skill_frontmatter(skill, allowed)


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


def plugin_version() -> str:
    """Resolve the semver stamped into the Codex plugin manifest.

    TODO(version-file): a later phase adds a top-level VERSION file that stamps
    every manifest. Read it here first when it exists, and keep this fallback
    only until plugin.json stops being the source of truth.
    """
    src = REPO_ROOT / CLAUDE_PLUGIN_MANIFEST
    try:
        version = json.loads(src.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError) as exc:
        raise AssembleError(f"cannot read {src}: {exc}") from exc
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        raise AssembleError(
            f"{src}: version must be MAJOR.MINOR.PATCH for the Codex cache key, "
            f"got {version!r}"
        )
    return version


CODEX_POSTTOOLUSE_MATCHER = "apply_patch"
CODEX_HOOKS_ROOT_KEYS = {"description", "hooks"}


def write_codex_hooks(plugin_dir: Path) -> None:
    """Rewrite the copied hooks.json for Codex's tool names.

    Only the PostToolUse matcher differs: Claude reports file writes as
    Write|Edit, Codex reports them as apply_patch. Deriving the Codex file from
    the Claude one keeps the SessionStart wiring from drifting, which matters
    because an untrusted or malformed Codex hooks file fails silently.
    """
    dest = plugin_dir / "hooks" / "hooks.json"
    data = json.loads(dest.read_text(encoding="utf-8"))
    unknown = sorted(set(data) - CODEX_HOOKS_ROOT_KEYS)
    if unknown:
        raise AssembleError(
            f"{dest}: root key(s) {', '.join(unknown)} would fail Codex's "
            "deny-unknown-fields parse; route them per harness"
        )
    for entry in data.get("hooks", {}).get("PostToolUse", []):
        if "matcher" in entry:
            entry["matcher"] = CODEX_POSTTOOLUSE_MATCHER
    dest.write_text(json.dumps(data, indent=2) + "\n")


def copy_codex_plugin(out: Path) -> None:
    """Copy plugins/llm-wiki into the Codex subtree, minus excluded paths.

    Deliberately a near-copy of copy_plugin. Two concrete emitters come first;
    the shared abstraction is extracted from them, not designed ahead of them.
    """
    src = (REPO_ROOT / "plugins" / PLUGIN_NAME).resolve()
    if not src.is_dir():
        raise AssembleError(f"missing plugin source: {src}")
    dest = out / "codex" / "plugins" / PLUGIN_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=plugin_ignore(src))
    # Claude's manifest must not ride along: Codex resolves .codex-plugin first
    # but falls back to .claude-plugin, and a stale second manifest is exactly
    # the silent-divergence trap that fallback creates.
    claude_manifest_dir = dest / ".claude-plugin"
    if not claude_manifest_dir.is_dir():
        raise AssembleError(
            f"expected {claude_manifest_dir} in the copied plugin tree"
        )
    shutil.rmtree(claude_manifest_dir)
    write_codex_plugin_manifest(dest)
    write_codex_hooks(dest)


def write_codex_plugin_manifest(plugin_dir: Path) -> None:
    """Generate .codex-plugin/plugin.json for the Codex subtree."""
    manifest = {
        "name": PLUGIN_NAME,
        "version": plugin_version(),
        "description": CODEX_PLUGIN_DESCRIPTION,
        "author": {
            "name": "LA3D-LLM-Agents",
            "url": "https://github.com/LA3D-LLM-Agents",
        },
    }
    dest = plugin_dir / ".codex-plugin" / "plugin.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2) + "\n")


def write_codex_marketplace(out: Path) -> None:
    """Generate .agents/plugins/marketplace.json for the Codex subtree."""
    catalog = {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": CODEX_MARKETPLACE_DISPLAY_NAME},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {"source": "local", "path": CODEX_PLUGIN_SOURCE},
                "description": CODEX_PLUGIN_DESCRIPTION,
            }
        ],
    }
    dest = out / ".agents" / "plugins" / "marketplace.json"
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

    # Claude subtree.
    write_marketplace(out, owner_repo)
    copy_plugin(out)
    strip_skill_frontmatter(out / "claude" / "plugins" / PLUGIN_NAME, CLAUDE_SKILL_KEYS)

    # Codex subtree.
    write_codex_marketplace(out)
    copy_codex_plugin(out)
    strip_skill_frontmatter(out / "codex" / "plugins" / PLUGIN_NAME, CODEX_SKILL_KEYS)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        out = resolve_out_dir(args.out)
        owner_repo = args.owner_repo or default_owner_repo()
        if owner_repo.count("/") != 1 or not all(owner_repo.split("/")):
            raise AssembleError(f"--owner-repo must be OWNER/REPO, got {owner_repo!r}")
        source_ref = args.source_ref or default_source_ref()
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
