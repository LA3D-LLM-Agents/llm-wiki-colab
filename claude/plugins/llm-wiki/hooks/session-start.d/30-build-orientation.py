"""Read memory after maintenance and add orientation to the shared response."""
import re
import subprocess

# Stamped by the index template; when several index_*.md files exist it
# distinguishes the wiki's catalog from pages whose names start with index_.
INDEX_MARKER = "Catalog of all wiki pages, organized by category."

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


def origin_name(root):
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root,
                            capture_output=True, text=True).stdout.strip()
    return origin.removesuffix(".git").rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1] if origin else root.name


def wiki_name(root, wiki, warnings):
    """Name the wiki was initialized under: the stem of its stamped index.

    The host origin is only a fallback; it can differ from the stamped name
    (--repo-name, origin renamed or added after init).
    """
    indexes = [p for p in sorted(wiki.glob("index_*.md")) if p.is_file()]
    if len(indexes) > 1:
        indexes = [p for p in indexes if INDEX_MARKER in p.read_text(errors="replace")]
    stems = [p.name[len("index_"):-len(".md")] for p in indexes]
    if len(stems) == 1:
        return stems[0]
    name = origin_name(root)
    if stems and name not in stems:
        warnings.append(f"llm-wiki: several wiki indexes found ({', '.join(stems)}); "
                        f"orienting on {name}, which is not among them.")
    return name


def run(state):
    root, wiki = state["project_root"], state["wiki_dir"]
    name = wiki_name(root, wiki, state["warnings"])
    log = wiki / f"log_{name}.md"
    if not (wiki / f"index_{name}.md").is_file() or not log.is_file():
        state["warnings"].append(f"llm-wiki: index_{name}.md or log_{name}.md is missing; "
                                 "the wiki snapshot below is incomplete.")
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
