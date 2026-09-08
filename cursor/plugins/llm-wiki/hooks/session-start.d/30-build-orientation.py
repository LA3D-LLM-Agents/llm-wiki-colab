"""Read memory after maintenance and add orientation to the shared response."""
import re
import subprocess

ORIENTATION = """<system-reminder>
This project uses the wiki at .llm-wiki/ as durable memory. It is a separate
git repository, NOT tracked by the main repo. Read
.llm-wiki/SCHEMA_{name}.md before non-trivial wiki edits. Update the wiki
proactively when experiment results, decisions, or syntheses emerge.

The local wiki's index (page catalog) and its last 5 log entries are included
in this session's context below. You already hold this local snapshot; see the refresh outcome for remote freshness:
treat the index as read, do not re-open index_{name}.md just to see what
pages exist or what changed recently. Open individual .llm-wiki/ page files only
when you need a page's actual contents.

Every wiki edit ends with a commit in the wiki's own repo:
  git -C .llm-wiki add <files>
  git -C .llm-wiki commit -m "..."
Run these without asking; local commits are reversible. Push only on explicit
request.

User-invocable skills: /wiki-init, /wiki-experiment, /wiki-source, /wiki-lint.
</system-reminder>"""


def run(state):
    root, wiki = state["project_root"], state["wiki_dir"]
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root,
                            capture_output=True, text=True).stdout.strip()
    name = origin.removesuffix(".git").rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1] if origin else root.name
    log = wiki / f"log_{name}.md"
    log_text = log.read_text() if log.is_file() else ""
    entries = list(re.finditer(r"^## \[", log_text, re.MULTILINE))
    pages = sum(1 for p in wiki.glob("*.md") if p.is_file())
    state["banner"] = f"llm-wiki: durable memory active in {name} ({pages} pages, {len(entries)} log entries)"
    state["context"].append(ORIENTATION.format(name=name))
    guidance = state["plugin_root"] / "core/templates/guidance.md"
    if guidance.is_file():
        state["context"].append("<system-reminder>\n" + guidance.read_text() + "\n</system-reminder>")
    index = wiki / f"index_{name}.md"
    if index.is_file():
        state["context"].append("<system-reminder>\n## Wiki current state: index\n\n" + index.read_text() + "\n</system-reminder>")
    if log.is_file():
        recent = log_text[entries[-5].start():] if len(entries) >= 5 else (log_text[entries[0].start():] if entries else "")
        state["context"].append("<system-reminder>\n## Wiki current state: last 5 log entries\n\n" + recent + "\n</system-reminder>")
