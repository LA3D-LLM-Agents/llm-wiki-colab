#!/usr/bin/env python3
"""Attach and scaffold wiki memory. Refresh and orientation belong to startup."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
NETWORK_TIMEOUT = 30


def repo_root(directory: Path) -> Path:
    result = subprocess.run(["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, check=True)
    return Path(result.stdout.strip())


def is_wiki_checkout(wiki: Path) -> bool:
    try:
        return wiki.is_dir() and repo_root(wiki).resolve() == wiki.resolve()
    except subprocess.CalledProcessError:
        return False


def origin_url(root: Path) -> str:
    # Derive identity before Git applies insteadOf transport rewrites. Git
    # still applies those rewrites itself when probing or cloning the wiki.
    result = subprocess.run(["git", "-C", str(root), "config", "--get", "remote.origin.url"],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def remote_parts(url: str) -> tuple[str, str]:
    """Return hostname and repo path for URL, SCP-style, or local origins."""
    if "://" in url:
        parts = urlsplit(url)
        return parts.hostname or "", parts.path.strip("/").removesuffix(".git")
    if ":" in url and not url.startswith("/"):
        host, path = url.split(":", 1)
        return host.rsplit("@", 1)[-1], path.strip("/").removesuffix(".git")
    return "", url.rstrip("/").removesuffix(".git")


def repo_name(root: Path) -> str:
    url = origin_url(root)
    return remote_parts(url)[1].rsplit("/", 1)[-1] if url else root.name


def github_wiki_urls(url: str) -> tuple[str, str]:
    host, path = remote_parts(url)
    if not (host == "github.com" or host.startswith("github.")) or len(path.split("/")) != 2:
        raise ValueError("origin must identify a GitHub owner/repository")
    return url.rstrip("/").removesuffix(".git") + ".wiki.git", f"https://{host}/{path}/wiki/_new"


class InitError(Exception):
    def __init__(self, status: str, message: str, **details):
        self.result = {"status": status, "message": message, **details}
        super().__init__(message)


def git(root: Path, *args: str, network: bool = False) -> str:
    env = dict(os.environ)
    if network:
        env.update(GIT_TERMINAL_PROMPT="0", GIT_SSH_COMMAND="ssh -oBatchMode=yes")
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, check=True, env=env,
                            timeout=NETWORK_TIMEOUT if network else None)
    return result.stdout.strip()


def has_schema(wiki: Path, name: str) -> bool:
    return (wiki / f"SCHEMA_{name}.md").is_file() or (wiki / "SCHEMA.md").is_file()


def attach(root: Path, wiki: Path) -> None:
    remote, setup_url = github_wiki_urls(origin_url(root))
    try:
        refs = git(root, "ls-remote", remote, network=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        # GitHub can return the same "not found" for an uninitialized wiki and
        # inaccessible private content. Do not turn an ambiguous failure into
        # permission to create a disconnected local repository.
        raise InitError(
            "remote-unavailable", "Could not access the wiki remote. Check authentication and network access. "
            "If Wiki is disabled or has no pages, enable it and create the first page at the setup URL, then rerun.",
            setup_url=setup_url, error=error_text(exc)) from exc
    if not refs:
        raise InitError("needs-first-page", "Enable Wiki and create its first page at the setup URL, then rerun.",
                        setup_url=setup_url)
    ensure_exclude(root)
    try:
        git(root, "clone", "--", remote, str(wiki), network=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InitError("clone-failed", "Cloning did not complete; inspect any partial attachment before rerunning.",
                        error=error_text(exc)) from exc


def ensure_exclude(root: Path) -> None:
    helper = runpy.run_path(str(HERE / "ensure-local-exclude.py"))
    helper["ensure_local_exclude"](root)


def render(template: str, values: dict[str, str]) -> str:
    # One substitution pass: user-provided titles are literal, never templates
    # or shell code. Uppercase placeholders are intentionally runtime values.
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: values[match[1]], template)


def scaffold(wiki: Path, name: str, title: str, agent: str, missing_templates_only: bool) -> list[str]:
    if git(wiki, "status", "--porcelain"):
        raise InitError("local-changes", "Scaffolding needs a clean wiki checkout. Preserve or commit its local work, then rerun.")
    # Fail before writing if Git cannot commit, and read attribution from the
    # wiki's own configuration rather than the host repository's config.
    git(wiki, "var", "GIT_AUTHOR_IDENT")
    git(wiki, "var", "GIT_COMMITTER_IDENT")
    user = git(wiki, "config", "user.name")
    values = {"REPO_NAME": name, "PROJECT_NAME": title, "DATE": date.today().isoformat(),
              "BY_LINE": f"- by: {user}" + (f" via {agent}" if agent else "")}
    templates = [ASSETS / "Edge-Types.md.template"] if missing_templates_only else sorted(ASSETS.glob("*.md.template"))
    if not templates:
        raise InitError("missing-assets", "Initialization templates are missing from this skill installation.")
    # Render everything first; a damaged asset should fail before any writes.
    pending = [(render(t.name.removesuffix(".template"), values), render(t.read_text(), values)) for t in templates]
    created = []
    for filename, body in pending:
        path = wiki / filename
        if os.path.lexists(path):
            continue
        with path.open("x") as output:
            output.write(body)
        created.append(filename)
    if not created:
        return []
    # Only named files created here can enter these commits. Keep the log in
    # its own commit, as required by the seeded attribution convention.
    log = f"log_{name}.md"
    pages = [filename for filename in created if filename != log]
    groups = [(pages, "Initialize wiki foundations"), ([log] if log in created else [], "Record wiki initialization")]
    try:
        for files, message in groups:
            if files:
                git(wiki, "add", "--", *files)
                git(wiki, "commit", "--only", "-m", message, "--", *files)
    except subprocess.CalledProcessError as exc:
        raise InitError("commit-failed", "Scaffold files were written but initialization commits are incomplete. "
                        "Resolve the Git error and commit these files before relying on setup being complete.",
                        files=created, error=error_text(exc)) from exc
    return created


def initialize(args, root: Path) -> dict:
    wiki = root / ".llm-wiki"
    name = args.repo_name or repo_name(root)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
        raise InitError("invalid-name", "Repository namespace must be a filename-safe repo name; use --repo-name.")
    attached = False
    if os.path.lexists(wiki):
        if not is_wiki_checkout(wiki):
            raise InitError("invalid-attachment", ".llm-wiki/ is not a separate Git checkout. Repair the attachment before initializing.")
        if has_schema(wiki, name) and not args.stamp_missing_templates:
            return {"status": "already-initialized"}
    else:
        if args.stamp_missing_templates:
            raise InitError("missing-attachment", "Attach the wiki before stamping missing templates.")
        if args.github:
            attach(root, wiki)
            attached = True
        else:
            ensure_exclude(root)
            git(root, "init", str(wiki))
        if not is_wiki_checkout(wiki):
            raise InitError("invalid-attachment", "The new .llm-wiki/ is not a separate Git checkout.")
    ensure_exclude(root)
    if has_schema(wiki, name) and not args.stamp_missing_templates:
        return {"status": "attached"}
    created = scaffold(wiki, name, args.name or name, args.agent, args.stamp_missing_templates)
    return {"status": "templates-stamped" if args.stamp_missing_templates else
            "attached-and-scaffolded" if attached else "scaffolded", "files": created}


def error_text(exc: Exception) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return "Git network operation timed out."
    if isinstance(exc, subprocess.CalledProcessError):
        return (exc.stderr or str(exc)).strip()
    return str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github", action="store_true", help="attach the GitHub wiki from origin; without this flag, initialize locally")
    parser.add_argument("--agent", default="", help="assistant name for the initialization log")
    parser.add_argument("--name", default="", help="human-facing project title")
    parser.add_argument("--repo-name", default="", help="override the repository namespace")
    parser.add_argument("--stamp-missing-templates", action="store_true", help="add only missing vocabulary templates to an attached wiki")
    args = parser.parse_args()
    wiki_path = None
    try:
        root = repo_root(Path.cwd())
        wiki_path = str(root / ".llm-wiki")
        result = initialize(args, root)
        code = 0
    except InitError as exc:
        result, code = exc.result, 1
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        result, code = {"status": "failed", "message": error_text(exc)}, 1
    if wiki_path:
        result["wiki_path"] = wiki_path
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
