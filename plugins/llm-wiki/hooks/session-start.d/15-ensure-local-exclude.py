"""Keep the wiki out of the host repository using Git's local excludes."""
import os
from pathlib import Path
import secrets
import subprocess


def ensure_local_exclude(repo_root: Path) -> None:
    def git(*args):
        return subprocess.run(["git", "-C", str(repo_root), *args],
                              capture_output=True, check=True)

    # --git-path resolves the shared info directory for linked worktrees too.
    path = Path(os.fsdecode(git("rev-parse", "--git-path", "info/exclude").stdout).rstrip("\n"))
    if not path.is_absolute():
        path = repo_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    content = path.read_bytes() if path.exists() else b""
    ignored = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "--no-index", "--quiet", ".llm-wiki/"],
        capture_output=True)
    if ignored.returncode == 0:
        return
    if ignored.returncode != 1:
        raise RuntimeError("Git could not check the wiki ignore rule")
    rule = b"/.llm-wiki/"
    if rule not in content.splitlines():
        newline = b"\r\n" if b"\r\n" in content else b"\n"
        separator = b"" if not content or content.endswith(b"\n") else newline
        # Written beside the file and renamed over it, so Git never reads a
        # partial file. Concurrent sessions each use their own name and write
        # the same content, so no lock is taken. The file is closed before the
        # rename because Windows refuses to replace or unlink an open file.
        scratch = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
        try:
            scratch.write_bytes(content + separator + rule + newline)
            if path.exists():
                os.chmod(scratch, path.stat().st_mode & 0o777)
            os.replace(scratch, path)
        finally:
            scratch.unlink(missing_ok=True)
    # A tracked .gitignore negation takes precedence over local excludes.
    git("check-ignore", "--no-index", "--quiet", ".llm-wiki/")


def run(state):
    try:
        ensure_local_exclude(state["project_root"])
    except (OSError, subprocess.CalledProcessError, RuntimeError):
        state["warnings"].append(
            "llm-wiki: could not ensure the local wiki ignore rule; "
            "check Git's ignore configuration before committing the host project.")
