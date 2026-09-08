"""Keep the wiki out of the host repository using Git's local excludes."""
import os
from pathlib import Path
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
    lock = path.with_name(path.name + ".lock")
    # Fail safely if another invocation is updating this file.
    with lock.open("xb") as output:
        replaced = False
        try:
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
                output.write(content + separator + rule + newline)
                output.flush()
                if path.exists():
                    os.fchmod(output.fileno(), path.stat().st_mode & 0o777)
                os.replace(lock, path)
                replaced = True
            # A tracked .gitignore negation takes precedence over local excludes.
            git("check-ignore", "--no-index", "--quiet", ".llm-wiki/")
        finally:
            if not replaced:
                lock.unlink(missing_ok=True)


def run(state):
    try:
        ensure_local_exclude(state["project_root"])
    except (OSError, subprocess.CalledProcessError, RuntimeError):
        state["warnings"].append(
            "llm-wiki: could not ensure the local wiki ignore rule; "
            "check Git's ignore configuration before committing the host project.")
