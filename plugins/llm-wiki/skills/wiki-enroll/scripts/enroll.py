#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML>=6,<7", "jsonschema>=4.18,<5"]
# ///
"""Prepare a versioned wiki card. Publishing and index verification are separate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

TRUSTED = {
    "la3d-llm-agents",
    "la3d",
    "crcresearch",
    "paperanalyticaldevicend",
    "chrissweet",
    "charlesvardeman",
    "psaboia",
}
IDENTITY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class EnrollError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def run(command, cwd=None):
    try:
        result = subprocess.run(
            command, cwd=cwd, text=True, capture_output=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        raise EnrollError("Command unavailable or timed out: " + command[0]) from None
    if result.returncode:
        # Git errors can contain credential-bearing origins; do not echo stderr.
        raise EnrollError("Command failed: " + " ".join(command[:3]))
    return result.stdout.strip()


def github_repo(remote):
    """Parse standard HTTPS/SSH GitHub origins without consulting the login account."""
    if remote.startswith("git@github.com:"):
        value = remote[len("git@github.com:") :]
    else:
        parsed = urlsplit(remote)
        if (
            parsed.hostname != "github.com"
            or parsed.scheme not in ("https", "ssh")
            or parsed.password
            or parsed.query
            or parsed.fragment
            or (
                parsed.username
                and not (parsed.scheme == "ssh" and parsed.username == "git")
            )
        ):
            raise EnrollError(
                "Origin is not a standard credential-free GitHub URL; supply --repo OWNER/REPO."
            )
        value = parsed.path.lstrip("/")
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if not IDENTITY.fullmatch(value):
        raise EnrollError(
            "Cannot determine GitHub owner/repository; supply --repo OWNER/REPO."
        )
    return value


def origin(root):
    try:
        return run(["git", "remote", "get-url", "origin"], root)
    except EnrollError:
        return None


def prompt(message, default=None, required=False):
    while True:
        try:
            value = input(message + (f" [{default}]" if default else "") + ": ").strip()
        except EOFError:
            raise EnrollError(
                "Input ended; use --non-interactive with explicit metadata."
            ) from None
        value = value or default
        if value or not required:
            return value or ""
        print("A value is required.", file=sys.stderr)


def json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise EnrollError("Cannot read valid JSON from " + str(path)) from None


def dependencies():
    try:
        import yaml
        from jsonschema import Draft202012Validator
    except ImportError:
        raise EnrollError(
            "Install uv and rerun enroll.sh, or install PyYAML and jsonschema for python3."
        ) from None
    return yaml, Draft202012Validator


def read_card(path, yaml):
    if path.is_symlink():
        raise EnrollError("Card must not be a symlink.")
    if not path.exists():
        return {}, "", None
    if not path.is_file():
        raise EnrollError("Card must be a regular file, not a symlink.")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        raise EnrollError(
            "Existing card has no complete YAML frontmatter; repair it first."
        )

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise EnrollError(
                    "Existing card has duplicate or non-string YAML keys."
                )
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping
    )
    try:
        metadata = yaml.load(match.group(1), Loader=UniqueLoader)
    except yaml.YAMLError:
        raise EnrollError(
            "Existing card contains invalid YAML; repair it first."
        ) from None
    if not isinstance(metadata, dict):
        raise EnrollError("Existing frontmatter must be an object.")
    return metadata, text[match.end() :], raw


def validate(card, validator):
    schema = json_file(
        Path(__file__).resolve().parents[1] / "references/agent-card-1.0.schema.json"
    )
    error = next(validator(schema).iter_errors(card), None)
    if error:
        where = ".".join(map(str, error.absolute_path)) or "card"
        raise EnrollError("Invalid structured card at " + where + ": " + error.message)
    if (
        len(card["description"]) > 4000
        or len(card["card_url"]) > 1000
        or any(len(part) > 100 for part in card["id"].split("/"))
        or any(len(skill["description"]) > 1000 for skill in card["skills"])
    ):
        raise EnrollError("Card exceeds the fabric importer's metadata limits.")
    for key in ("skills", "knowledge_bundles", "interfaces"):
        ids = [item["id"] for item in card[key]]
        if len(ids) > 100 or len(ids) != len(set(ids)):
            raise EnrollError("Too many or duplicate IDs in " + key)
    bundles = {b["id"] for b in card["knowledge_bundles"]}
    for interface in card["interfaces"]:
        if (
            interface["kind"] == "clone-and-invoke"
            and interface["bundle_id"] not in bundles
        ):
            raise EnrollError("Unknown bundle_id in interface " + interface["id"])


def check_existing(metadata, validator):
    for key in ("id", "description"):
        if key in metadata and not isinstance(metadata[key], str):
            raise EnrollError("Existing " + key + " must be a string.")
    for key in ("capabilities", "topics"):
        if key in metadata and (
            not isinstance(metadata[key], list)
            or any(not isinstance(v, str) for v in metadata[key])
        ):
            raise EnrollError("Existing " + key + " must be a list of strings.")
    x = metadata.get("x-llm-wiki", {})
    if not isinstance(x, dict):
        raise EnrollError("Existing x-llm-wiki must be an object.")
    if "topics" in x and (
        not isinstance(x["topics"], list)
        or any(not isinstance(v, str) for v in x["topics"])
    ):
        raise EnrollError("Existing x-llm-wiki.topics must be a list of strings.")
    if "x-fabric-card" in metadata:
        card = metadata["x-fabric-card"]
        validate(card, validator)
        for key, value in [
            ("id", card["id"]),
            ("description", card["description"]),
            ("capabilities", [s["description"] for s in card["skills"]]),
        ]:
            if key in metadata and metadata[key] != value:
                raise EnrollError(
                    "Existing "
                    + key
                    + " conflicts with x-fabric-card; reconcile it first."
                )


def make_skills(capabilities):
    if len(capabilities) != len(set(capabilities)):
        raise EnrollError(
            "Duplicate capability descriptions; provide distinct skills with --skills-json."
        )
    return [
        {
            "id": "skill-" + hashlib.sha256(text.encode()).hexdigest()[:16],
            "name": text,
            "description": text,
            "tags": [],
        }
        for text in capabilities
    ]


def write_atomic(path, content, previous):
    fd, name = tempfile.mkstemp(prefix=".enroll-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if (
            path.is_symlink()
            or (path.read_bytes() if path.exists() else None) != previous
        ):
            raise EnrollError(
                "Card changed while preparing the update; rerun against the new contents."
            )
        os.chmod(name, path.stat().st_mode & 0o777 if previous is not None else 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def execute(args):
    try:
        root = Path(
            run(["git", "rev-parse", "--show-toplevel"], args.repo_root)
        ).resolve()
    except EnrollError:
        raise EnrollError("Not in a git repository.", 12) from None
    wiki = (root / (args.wiki_dir or ".llm-wiki")).resolve()
    if not wiki.is_dir():
        raise EnrollError(
            "Wiki directory is missing; attach it with wiki-init or supply --wiki-dir.",
            9,
        )
    if (
        Path(run(["git", "rev-parse", "--show-toplevel"], wiki)).resolve() != wiki
        or wiki == root
    ):
        raise EnrollError("Wiki must be a separate Git checkout.", 9)
    repo = args.repo or github_repo(origin(root) or "")
    if not IDENTITY.fullmatch(repo) or repo.endswith(".wiki"):
        raise EnrollError("--repo must name the host GitHub OWNER/REPO, not its wiki.")
    owner, name = repo.split("/")
    wiki_origin = origin(wiki)
    if wiki_origin and github_repo(wiki_origin).lower() != (repo + ".wiki").lower():
        raise EnrollError(
            "Wiki origin does not match the selected host repository; attach the correct wiki."
        )
    if args.add_topic and not wiki_origin:
        raise EnrollError("Attach the GitHub wiki before adding a discovery topic.")
    if args.check_remote:
        if not wiki_origin:
            raise EnrollError("Cannot check publication: wiki has no origin.")
        run(["git", "ls-remote", "--exit-code", "origin", "HEAD"], wiki)
    target = wiki / ("Card_" + name + ".md")
    if not target.exists() and list(wiki.glob("Card_*.md")):
        raise EnrollError(
            "Other card pages exist but "
            + target.name
            + " is missing; resolve the publication filename explicitly before enrollment."
        )
    yaml, validator = dependencies()
    metadata, body, previous = read_card(target, yaml)
    check_existing(metadata, validator)
    expected_url = "https://github.com/" + repo + "/wiki/" + target.stem
    if metadata.get("x-fabric-card", {}).get("card_url", expected_url) != expected_url:
        raise EnrollError(
            "Existing card_url does not match its discovered publication location."
        )
    if previous is not None and not args.update:
        if (
            args.card_json
            or args.skills_json
            or args.description
            or args.name
            or args.agent_id
            or args.topic is not None
            or args.capability
        ):
            raise EnrollError("Card already exists; use --update to change it.")
        print("Card unchanged: " + str(target) + " (use --update to migrate or edit).")
        return finish(args, repo, wiki, target, wiki_origin, changed=False)
    old_card = metadata.get("x-fabric-card")
    old_id = old_card["id"] if old_card else metadata.get("id")
    requested = json_file(args.card_json) if args.card_json else None
    if requested is not None:
        validate(requested, validator)
    identity = args.agent_id or (requested or {}).get("id") or old_id or repo
    if old_id and identity != old_id:
        raise EnrollError("Existing agent identity cannot be renamed by enrollment.")
    if not IDENTITY.fullmatch(identity):
        raise EnrollError("Agent ID must be OWNER/NAME.")
    card_url = "https://github.com/" + repo + "/wiki/" + target.stem
    card = copy.deepcopy(requested or old_card or {})
    if not card:
        card = {
            "schema_version": "1.0",
            "id": identity,
            "name": args.name or name,
            "description": metadata.get("description", ""),
            "card_url": card_url,
            "skills": make_skills(metadata.get("capabilities", [])),
            "knowledge_bundles": [],
            "interfaces": [],
        }
        if wiki_origin:
            card["knowledge_bundles"] = [
                {"id": "project-wiki", "url": "https://github.com/" + repo + "/wiki"}
            ]
            card["interfaces"] = [
                {
                    "id": "wiki-ask",
                    "kind": "clone-and-invoke",
                    "url": "https://github.com/" + repo + ".wiki.git",
                    "bundle_id": "project-wiki",
                }
            ]
    if card["id"] != identity or card["card_url"] != card_url:
        raise EnrollError(
            "Structured identity/card_url must match the preserved ID and discovered card location."
        )
    if args.name is not None:
        card["name"] = args.name
    if args.description is not None:
        card["description"] = args.description
    if not card["description"].strip():
        if args.non_interactive:
            raise EnrollError(
                "Missing description; supply --description or --card-json."
            )
        card["description"] = prompt("Describe this agent", required=True)
    if args.skills_json:
        card["skills"] = json_file(args.skills_json)
    elif args.capability:
        if old_card:
            raise EnrollError(
                "Use --skills-json with the existing skill IDs to edit structured skills."
            )
        card["skills"] = make_skills(args.capability)
    if not card["skills"]:
        if args.non_interactive:
            raise EnrollError(
                "At least one skill is required; supply --capability, --skills-json or --card-json."
            )
        capabilities = [prompt("First capability", required=True)]
        while True:
            value = prompt("Another capability (empty finishes)")
            if not value:
                break
            capabilities.append(value)
        card["skills"] = make_skills(capabilities)
    validate(card, validator)
    if old_card and not {s["id"] for s in old_card["skills"]}.issubset(
        {s["id"] for s in card["skills"]}
    ):
        raise EnrollError(
            "Existing skill IDs must be retained; enrollment does not remove or rename skills."
        )
    topics = args.topic
    if topics is None:
        topics = metadata.get("x-llm-wiki", {}).get(
            "topics", metadata.get("topics", [])
        )
        if previous is None and not args.non_interactive:
            topics = [
                s.strip()
                for s in prompt("Topics separated by commas (optional)").split(",")
                if s.strip()
            ]
    if len(topics) > 100 or any(len(topic) > 1000 for topic in topics):
        raise EnrollError("Topics exceed the fabric importer's metadata limits.")
    result = copy.deepcopy(metadata)
    result.setdefault("type", "agent")
    if "up" not in result:
        homes = sorted(wiki.glob("Home_*.md"))
        home = wiki / ("Home_" + name + ".md")
        if not home.exists():
            if len(homes) != 1:
                raise EnrollError(
                    "Cannot choose a Home page; initialize the wiki or set up in the existing card."
                )
            home = homes[0]
        result["up"] = "[[" + home.stem + "]]"
    result.update(
        id=identity,
        description=card["description"],
        capabilities=[s["description"] for s in card["skills"]],
    )
    result.setdefault("x-llm-wiki", {})["topics"] = topics
    if "topics" in result:
        result["topics"] = topics
    result["x-fabric-card"] = card
    if previous is None:
        body = "\n# Agent: " + identity + "\n\n" + card["description"] + "\n"
    serialized = yaml.safe_dump(result, sort_keys=False, allow_unicode=True)
    content = ("---\n" + serialized + "---\n" + body).encode("utf-8")
    # Serialization must retain the exact mapping we validated, including punctuation.
    if yaml.safe_load(serialized) != result:
        raise EnrollError("YAML serialization did not roundtrip.")
    changed = content != previous
    if args.dry_run:
        print(content.decode(), end="")
        print("\nDRY RUN: no card or GitHub changes.", file=sys.stderr)
    elif changed:
        if not args.non_interactive:
            print(content.decode(), end="")
        if not args.non_interactive and prompt("Write this card? y/N").lower() not in (
            "y",
            "yes",
        ):
            print("Cancelled; no card or topic changes.")
            return 0
        write_atomic(target, content, previous)
        print("Card prepared locally: " + str(target))
    else:
        print("Card unchanged: " + str(target))
    return finish(args, repo, wiki, target, wiki_origin, changed)


def finish(args, repo, wiki, target, wiki_origin, changed):
    if args.add_topic:
        if not wiki_origin:
            raise EnrollError(
                "Card is only a local draft: attach its GitHub wiki before adding a topic."
            )
        if repo.split("/")[0].lower() not in TRUSTED:
            print(
                "Owner is not in the known index allowlist; a topic alone will not make it discoverable.",
                file=sys.stderr,
            )
        command = ["gh", "repo", "edit", repo, "--add-topic", "nd-llm-wiki"]
        if args.dry_run:
            print("Would run: " + shlex.join(command), file=sys.stderr)
        else:
            try:
                run(command)
            except EnrollError:
                raise EnrollError(
                    "Card preparation completed locally, but topic registration failed; rerun --add-topic after fixing gh access."
                ) from None
            print("Discovery topic added; index inclusion has not been verified.")
    print("Publication: not performed. Index inclusion: not verified.")
    print(
        "Wiki remote: "
        + (
            "access checked"
            if args.check_remote
            else "configured; access not checked"
            if wiki_origin
            else "not configured; local draft only"
        )
    )
    if changed and not args.dry_run:
        print("To stage and publish only this card:")
        for command in (
            ["git", "-C", str(wiki), "add", "--", target.name],
            [
                "git",
                "-C",
                str(wiki),
                "commit",
                "--only",
                "-m",
                "Update agent card",
                "--",
                target.name,
            ],
        ):
            print("  " + shlex.join(command))
        if wiki_origin:
            print("  " + shlex.join(["git", "-C", str(wiki), "push"]))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--repo",
        help="Explicit GitHub OWNER/REPO; default: origin, never the logged-in user",
    )
    parser.add_argument(
        "--wiki-dir",
        help="Wiki checkout, absolute or relative to host root; default .llm-wiki",
    )
    parser.add_argument(
        "--agent-id", help="New-card identity override; existing IDs cannot be renamed"
    )
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument(
        "--topic",
        action="append",
        help="Repeat to replace topics; omitted preserves existing topics",
    )
    parser.add_argument(
        "--capability",
        action="append",
        help="Description of an initial skill; repeat for multiple skills",
    )
    parser.add_argument(
        "--skills-json", type=Path, help="JSON array of skills; retain existing IDs"
    )
    parser.add_argument(
        "--card-json", type=Path, help="Complete x-fabric-card object; schema 1.0"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update/migrate the existing card, preserving its body and unrelated metadata",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Never prompt; fail clearly on missing metadata",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print candidate without writing cards or changing GitHub topics",
    )
    parser.add_argument(
        "--add-topic",
        action="store_true",
        help="Explicitly add nd-llm-wiki using gh; default does not change topics",
    )
    parser.add_argument(
        "--check-remote",
        action="store_true",
        help="Read-only wiki-origin access check; no remote URLs printed",
    )
    args = parser.parse_args()
    try:
        return execute(args)
    except (EnrollError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return getattr(exc, "code", 1)


if __name__ == "__main__":
    sys.exit(main())
