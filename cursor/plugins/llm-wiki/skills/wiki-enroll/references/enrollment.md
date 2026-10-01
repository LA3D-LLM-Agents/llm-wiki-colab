# Enrollment helper contract

Requires Git and Python 3.9+. With `uv` on PATH, `enroll.sh` runs the helper in an
isolated dependency environment using the selected `python3`. Without uv, that
Python must have PyYAML 6 and jsonschema 4 installed. `gh` is required only for
`--add-topic`. The wrapper resolves its own installed directory on every harness;
it does not depend on `CLAUDE_PLUGIN_ROOT`.

Run `scripts/enroll.sh` relative to this skill directory. Example arguments:

```sh
scripts/enroll.sh --non-interactive --dry-run \
  --description 'Explain our project: methods and results.' \
  --capability 'Explain: experiments and recorded evidence' --topic research
scripts/enroll.sh --non-interactive --update --description 'Revised project scope.'
scripts/enroll.sh --non-interactive --update --skills-json /path/to/skills.json
scripts/enroll.sh --non-interactive --update --card-json /path/to/card.json
```

`--card-json` accepts the complete **contents** of `x-fabric-card`, not a wrapper.
Its [vendored schema](agent-card-1.0.schema.json) is copied unchanged from
LA3D-LLM-Agents/ns commit `7650c279b1cc03750cc14722460d78030f86c8e6`,
`examples/agent-card.schema.json`. Fields are `schema_version: "1.0"`, `id`,
`name`, `description`, `card_url`, `skills`, `knowledge_bundles`, and `interfaces`.
Skill objects require `id`, `name`, `description`, and `tags`. A skill-input example:

```json
[{"id":"explain-project","name":"Explain the project","description":"Explain methods and recorded results","tags":["research"]}]
```

For updates, retain every existing skill ID when editing descriptions or names.
The helper rejects removing or renaming existing skill IDs. It never re-slugs
IDs from edited names. Legacy capabilities have no authored IDs: migration assigns
stable content-derived IDs, or accepts reviewed skills through JSON. New cards
need at least one skill. An existing legacy card without capabilities needs
explicit skill input to migrate. Conflicting old/new fields and malformed YAML
must be reconciled before writing. Unknown schema versions are rejected.

`--topic` is repeatable; if supplied it replaces the topic list. Omission preserves
existing topics. Other frontmatter, `x-llm-wiki` custom keys and the Markdown body
remain intact. YAML serialization is safe for colons, quotes, Unicode and newlines.
Updates use a same-directory atomic replacement and reject a detected concurrent
edit. An unchanged candidate is not rewritten. Existing cards without `--update`
are left alone; change flags require `--update`. EOF exits with an error instead
of treating it as confirmation or looping.

Repository detection accepts standard GitHub HTTPS and SSH origins. `--repo`
is the explicit escape hatch for SSH aliases, absent origins and offline work;
it does not rename an existing agent. `--wiki-dir` is absolute or relative to the
host root and must identify a separate Git checkout. A configured wiki origin
must belong to the selected host repository. A wiki without an origin can hold a
local draft, but the helper does not invent a clone route or claim publication.
A new card links the matching Home page, or the sole existing namespaced Home.
If another card filename exists but the canonical repository filename is absent,
the helper stops for resolution rather than creating a second identity silently.

Default generation adds a separate project-wiki bundle and clone-and-invoke
interface only when the wiki origin is configured. It adds no A2A or MCP endpoint.
Existing structured interfaces/bundles remain unchanged unless explicitly supplied
in a replacement structured JSON object. Legacy compatibility fields are generated
from the structured card so current readers can still consume its description,
capabilities and topics.

`--dry-run` writes no card and performs no GitHub mutations; it still reads local
Git state and may obtain Python dependencies. `--check-remote` explicitly performs
a read-only Git access check even in dry-run. Without it remote accessibility is
reported as unchecked. `--add-topic` targets the selected `OWNER/REPO` explicitly;
its dry-run prints the command. Registration failure returns nonzero and reports
that any already-prepared card remains local. No mailbox setup is performed.

The printed staging and `commit --only` commands name only the card, preserving
unrelated staged work. Push remains a separate operation. Distinguish:

1. Local card preparation.
2. Wiki commit and publication.
3. Discovery topic registration (if needed; org repositories are walked directly).
4. Verified index inclusion at the actual card URL.

Do not claim step 4 from success at steps 1–3. New structured publication should
follow compatible-reader deployment. No enrollment command upgrades the fabric
server, connector runtime or federation index builder.
