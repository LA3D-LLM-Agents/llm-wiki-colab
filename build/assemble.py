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
from collections.abc import Callable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"

MARKETPLACE_NAME = "llm-wiki-colab"
PLUGIN_NAME = "llm-wiki"
MARKETPLACE_DESCRIPTION = (
    "LLM-wiki durable-memory plugins for Claude Code, Codex, and Cursor."
)
PLUGIN_DESCRIPTION = (
    "Opt-in per-repo llm-wiki memory for Claude Code: SessionStart orientation "
    "(index + last-5 log) and a verification-gate advisory."
)
PLUGIN_SOURCE = "./claude/plugins/llm-wiki"
CODEX_PLUGIN_SOURCE = "./codex/plugins/llm-wiki"
CODEX_MARKETPLACE_DISPLAY_NAME = "LLM-wiki Colab"
CODEX_PLUGIN_DESCRIPTION = (
    "Opt-in per-repo llm-wiki memory for Codex: SessionStart orientation "
    "(index + last-5 log) and a verification-gate advisory."
)
CURSOR_PLUGIN_SOURCE = "./cursor/plugins/llm-wiki"
CURSOR_PLUGIN_DESCRIPTION = (
    "Opt-in per-repo llm-wiki memory for Cursor: sessionStart orientation "
    "(index + last-5 log) and a verification-gate advisory."
)
VERSION_FILE = Path("VERSION")
# Relative to a plugin directory, not to the repo root: after phase 4 the only
# manifest that gets read is the emitted one, to stamp it.
CLAUDE_MANIFEST_REL = Path(".claude-plugin/plugin.json")
# (0|[1-9]\d*) rather than \d+: semver forbids leading zeros, and Codex uses
# the string as a cache directory name.
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")

EXCLUDED_NAMES = {".DS_Store", "__pycache__"}
# Runtime-only directories that must never ride into the artifact tree.
# Empty today; the mechanism stays for the next gitignored build/cache dir.
EXCLUDED_PLUGIN_SUBPATHS: set[Path] = set()

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
# Cursor owns no key of its own, and universal-only routing is the point rather
# than an accident: a skill whose frontmatter carries disable-model-invocation
# is suppressed outright on Cursor, neither listed nor invocable by anyone
# (probed by mutation, cursor-agent 2026.08.11 — stripping the key from one
# installed skill made exactly that skill appear).
CURSOR_ONLY_SKILL_KEYS: set[str] = set()

CLAUDE_SKILL_KEYS = UNIVERSAL_SKILL_KEYS | CLAUDE_ONLY_SKILL_KEYS
CODEX_SKILL_KEYS = UNIVERSAL_SKILL_KEYS | CODEX_ONLY_SKILL_KEYS
CURSOR_SKILL_KEYS = UNIVERSAL_SKILL_KEYS | CURSOR_ONLY_SKILL_KEYS
KNOWN_SKILL_KEYS = CLAUDE_SKILL_KEYS | CODEX_SKILL_KEYS | CURSOR_SKILL_KEYS

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


def render_repo_file(name: str, out: Path, tokens: dict[str, str]) -> None:
    """Hydrate a repo-root file's {{token}} placeholders into the output tree.

    CITATION.cff has to stay a real, valid file at the repo root so GitHub's
    cite button finds it, and it has to carry the version. Hydration is the
    repo's existing dependency-free way to do that, and scan_for_tokens fails
    the build if a placeholder ever survives.
    """
    src = REPO_ROOT / name
    if not src.is_file():
        raise AssembleError(f"missing repo file: {src}")
    (out / name).write_text(
        hydrate(src.read_text(encoding="utf-8"), tokens, str(src)), encoding="utf-8"
    )


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


def emit_plugin_subtree(
    out: Path,
    harness: str,
    version: str,
    *,
    write_native_manifest: Callable[[Path, str], None],
    skill_keys: set[str],
    keep_claude_manifest: bool = False,
    transform_hooks: Callable[[Path], None] | None = None,
) -> None:
    """Emit one harness's plugin subtree.

    The shared spine of the three emitters: copy the plugin tree, prune the
    foreign manifest dir, write the native manifest, apply the harness's hook
    transforms, strip skill frontmatter to the keys that harness reads.

    The copied .claude-plugin/ is pruned wherever it is not the native
    manifest: Codex's and Cursor's undocumented fallback chains can resolve a
    stale Claude manifest riding along, which is exactly the silent-divergence
    trap the pruning closes.
    """
    src = (REPO_ROOT / "plugins" / PLUGIN_NAME).resolve()
    if not src.is_dir():
        raise AssembleError(f"missing plugin source: {src}")
    dest = out / harness / "plugins" / PLUGIN_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=plugin_ignore(src))
    if not keep_claude_manifest:
        claude_manifest_dir = dest / ".claude-plugin"
        if not claude_manifest_dir.is_dir():
            raise AssembleError(
                f"expected {claude_manifest_dir} in the copied plugin tree"
            )
        shutil.rmtree(claude_manifest_dir)
    write_native_manifest(dest, version)
    if transform_hooks is not None:
        transform_hooks(dest)
    strip_skill_frontmatter(dest, skill_keys)


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
                    "CLAUDE_ONLY_SKILL_KEYS, CODEX_ONLY_SKILL_KEYS, or "
                    "CURSOR_ONLY_SKILL_KEYS"
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


def read_version() -> str:
    """Read the repo's single version, from the top-level VERSION file.

    Every emitted manifest is stamped from this one read. Codex keys its
    install cache on the manifest version and nothing else, so a malformed or
    missing version has to fail the build rather than ship.
    """
    src = REPO_ROOT / VERSION_FILE
    try:
        raw = src.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssembleError(f"cannot read {src}: {exc}") from exc
    version = raw.strip()
    if not SEMVER_RE.match(version):
        raise AssembleError(
            f"{src}: version must be a single MAJOR.MINOR.PATCH line, got {raw!r}"
        )
    return version


def stamp_claude_plugin_manifest(plugin_dir: Path, version: str) -> None:
    """Stamp the version into the copied Claude plugin manifest.

    The source manifest deliberately carries no version field: VERSION is the
    only place a version is written by hand.
    """
    dest = plugin_dir / CLAUDE_MANIFEST_REL
    try:
        manifest = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssembleError(f"cannot read {dest}: {exc}") from exc
    if "version" in manifest:
        raise AssembleError(
            f"{REPO_ROOT / 'plugins' / PLUGIN_NAME / CLAUDE_MANIFEST_REL}: "
            "remove the version field; VERSION is the single source of truth"
        )
    stamped = {"name": manifest.pop("name", PLUGIN_NAME), "version": version, **manifest}
    dest.write_text(json.dumps(stamped, indent=2) + "\n", encoding="utf-8")


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


def write_codex_plugin_manifest(plugin_dir: Path, version: str) -> None:
    """Generate .codex-plugin/plugin.json for the Codex subtree."""
    manifest = {
        "name": PLUGIN_NAME,
        "version": version,
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


# Cursor's own hooks dialect: lowercase event names, one flat list of hook
# definitions per event, and a schema `version`. ${CURSOR_PLUGIN_ROOT} is
# expanded textually here and nowhere else in the tree, so the adapters are
# handed their own root as an argument.
CURSOR_HOOKS = {
    "version": 1,
    "hooks": {
        "sessionStart": [
            {
                "type": "command",
                "command": (
                    'bash "${CURSOR_PLUGIN_ROOT}/hooks/cursor-session-start.sh" '
                    '"${CURSOR_PLUGIN_ROOT}"'
                ),
            }
        ],
        "preToolUse": [
            {
                "type": "command",
                "matcher": "Shell",
                "command": (
                    'bash "${CURSOR_PLUGIN_ROOT}/hooks/cursor-pre-tool-use.sh" '
                    '"${CURSOR_PLUGIN_ROOT}"'
                ),
            }
        ],
        "postToolUse": [
            {
                "type": "command",
                "matcher": "Write|Edit",
                "command": (
                    'bash "${CURSOR_PLUGIN_ROOT}/hooks/cursor-post-tool-use.sh" '
                    '"${CURSOR_PLUGIN_ROOT}"'
                ),
            }
        ],
    },
}
# template name -> path inside the plugin, for the scripts Cursor's hooks.json
# points at. All are installed 0755: a non-executable hook script is the
# classic silent-no-hook failure.
CURSOR_ADAPTERS = {
    "cursor-session-start.sh": Path("hooks/cursor-session-start.sh"),
    "cursor-pre-tool-use.sh": Path("hooks/cursor-pre-tool-use.sh"),
    "cursor-post-tool-use.sh": Path("hooks/cursor-post-tool-use.sh"),
}


def write_cursor_hooks(plugin_dir: Path) -> None:
    """Replace the copied hooks.json with Cursor's dialect, and ship the adapters.

    Unlike the Codex file this is not derived from the Claude one: no field of
    the Claude dialect survives translation. SessionStart and post-write output
    reach Cursor through adapters to its additional_context field.
    The preToolUse entry has no Claude counterpart at all:
    it exists to put CLAUDE_PLUGIN_ROOT into the shell the agent runs skill
    commands in.
    """
    dest = plugin_dir / "hooks" / "hooks.json"
    if not dest.is_file():
        raise AssembleError(f"expected {dest} in the copied plugin tree")
    dest.write_text(json.dumps(CURSOR_HOOKS, indent=2) + "\n")

    for template, rel in CURSOR_ADAPTERS.items():
        src = TEMPLATE_DIR / template
        if not src.is_file():
            raise AssembleError(f"missing template: {src}")
        adapter = plugin_dir / rel
        shutil.copyfile(src, adapter)
        adapter.chmod(0o755)


def write_cursor_plugin_manifest(plugin_dir: Path, version: str) -> None:
    """Generate .cursor-plugin/plugin.json for the Cursor subtree.

    Cursor reads no version, but stamping it keeps one number describing one
    build across all three subtrees.
    """
    manifest = {
        "name": PLUGIN_NAME,
        "version": version,
        "description": CURSOR_PLUGIN_DESCRIPTION,
        "author": {
            "name": "LA3D-LLM-Agents",
            "url": "https://github.com/LA3D-LLM-Agents",
        },
    }
    dest = plugin_dir / ".cursor-plugin" / "plugin.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2) + "\n")


def write_cursor_marketplace(out: Path, owner_repo: str) -> None:
    """Generate .cursor-plugin/marketplace.json for the Cursor subtree.

    Cursor nests the catalog description under `metadata`, as Claude does, and
    carries the same `owner` block. The two names are deliberately identical to
    the Claude catalog's: Cursor imports Claude-installed plugins and dedupes on
    marketplaceName/pluginName, so any per-harness rename gives a dual-harness
    user two copies whose hooks both fire.
    """
    owner = owner_repo.split("/", 1)[0]
    catalog = {
        "name": MARKETPLACE_NAME,
        "owner": {"name": owner, "url": f"https://github.com/{owner}"},
        "metadata": {"description": MARKETPLACE_DESCRIPTION},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": CURSOR_PLUGIN_SOURCE,
                "description": CURSOR_PLUGIN_DESCRIPTION,
            }
        ],
    }
    dest = out / ".cursor-plugin" / "marketplace.json"
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


def assemble(out: Path, owner_repo: str, source_ref: str, version: str) -> None:
    """Emit the full artifact tree into an already-validated output directory."""
    tokens = {
        "owner_repo": owner_repo,
        "source_ref": source_ref,
        "version": version,
    }
    reset_dir(out)
    render_template("readme.md", out / "README.md", tokens)
    copy_repo_file("LICENSE", out)
    render_repo_file("CITATION.cff", out, tokens)
    # The artifact tree states its own version at a fixed, platform-neutral
    # path. build/publish.py reads this file out of the parent commit to decide
    # whether a publish carries a bump.
    (out / VERSION_FILE).write_text(version + "\n", encoding="utf-8")

    # Claude subtree. The native manifest is the copied one, stamped.
    write_marketplace(out, owner_repo)
    emit_plugin_subtree(
        out,
        "claude",
        version,
        write_native_manifest=stamp_claude_plugin_manifest,
        skill_keys=CLAUDE_SKILL_KEYS,
        keep_claude_manifest=True,
    )

    # Codex subtree.
    write_codex_marketplace(out)
    emit_plugin_subtree(
        out,
        "codex",
        version,
        write_native_manifest=write_codex_plugin_manifest,
        skill_keys=CODEX_SKILL_KEYS,
        transform_hooks=write_codex_hooks,
    )

    # Cursor subtree.
    write_cursor_marketplace(out, owner_repo)
    emit_plugin_subtree(
        out,
        "cursor",
        version,
        write_native_manifest=write_cursor_plugin_manifest,
        skill_keys=CURSOR_SKILL_KEYS,
        transform_hooks=write_cursor_hooks,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        out = resolve_out_dir(args.out)
        owner_repo = args.owner_repo or default_owner_repo()
        if owner_repo.count("/") != 1 or not all(owner_repo.split("/")):
            raise AssembleError(f"--owner-repo must be OWNER/REPO, got {owner_repo!r}")
        source_ref = args.source_ref or default_source_ref()
        version = read_version()
        assemble(out, owner_repo, source_ref, version)
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
    print(f"version:    {version}")
    print(f"files:      {count_files(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
