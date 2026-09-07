"""Real local Git remotes and evidence for installed startup stage ordering."""

import subprocess

from .plugin_orientation import OrientationSeed, orientation_evidence, seed_wiki
from .skill_assertions import audit_messages

DIVERGED = "Wiki refresh incomplete: fetched upstream but could not fast-forward the checkout."
DIRTY = "Wiki refresh skipped: local changes preserved;"
FETCH_FAILED = "Wiki refresh failed: fetch failed or timed out;"
NO_REMOTE = "Wiki refresh skipped: no origin remote configured;"
INVALID = ".llm-wiki/ is not a separate Git checkout."


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def commit(repo, message):
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Probe", "-c", "user.email=probe@example.test",
        "commit", "-qm", message)


def seed_remote_wiki(root, workspace, *, diverged):
    """Leave the wiki clean and behind a local remote; never call a hook here."""
    initial = OrientationSeed.fresh()
    seed_wiki(workspace, initial)
    wiki = workspace / ".llm-wiki"
    commit(wiki, "initial memory")
    git(wiki, "branch", "-M", "main")
    remote = root / "wiki.git"
    subprocess.run(["git", "clone", "--bare", str(wiki), str(remote)],
                   check=True, capture_output=True)
    git(wiki, "remote", "add", "origin", str(remote))
    git(wiki, "fetch", "origin")
    git(wiki, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    writer = root / "remote-writer"
    subprocess.run(["git", "clone", str(remote), str(writer)], check=True, capture_output=True)
    updated = OrientationSeed.fresh()
    # Keep the log/page/schema fixed so the index marker isolates freshness.
    updated = OrientationSeed(updated.index, initial.logs, initial.page, initial.schema)
    (writer / "index_orientation-probe.md").write_text(f"# Index\n\n{updated.index}\n")
    commit(writer, "remote index update")
    git(writer, "push", "origin", "main")
    if diverged:
        (wiki / "local-only.md").write_text("preserve local committed work\n")
        commit(wiki, "local work")
    return initial, updated, git(wiki, "rev-parse", "HEAD"), git(writer, "rev-parse", "HEAD")


def startup_evidence(transcript, request, output, seed, guidance, *, scenario,
                     excluded_index=None, evidence_source="API request"):
    audit_messages(transcript)
    if request.calls or request.results:
        raise RuntimeError("startup request contains tool activity")
    incoming = "\n".join(text for _, text in request.incoming)
    expected_warning = {"invalid": INVALID, "diverged": DIVERGED, "dirty": DIRTY,
                        "fetch_failed": FETCH_FAILED, "no_remote": NO_REMOTE}.get(scenario)
    normalized = lambda text: " ".join(text.replace("\\n", " ").split())
    if expected_warning:
        for text in (incoming, output):
            if normalized(expected_warning) not in normalized(text):
                raise RuntimeError("startup warning absent from incoming context or recovery")
    elif any(warning in incoming for warning in (INVALID, DIVERGED, DIRTY, FETCH_FAILED, NO_REMOTE)):
        raise RuntimeError("unexpected startup warning")
    if scenario == "invalid":
        if "Every wiki edit ends with a commit" in incoming:
            raise RuntimeError("invalid attachment received wiki editing instructions")
        result = orientation_evidence(transcript, request, output, seed, guidance,
                                      opted_in=False, evidence_source=evidence_source)
    else:
        result = orientation_evidence(transcript, request, output, seed, guidance,
                                      opted_in=True, evidence_source=evidence_source)
    if excluded_index and (excluded_index in incoming or excluded_index in output):
        raise RuntimeError("wrong checkout version delivered to model")
    return result | {"scenario": scenario, "warning_received": bool(expected_warning)}
