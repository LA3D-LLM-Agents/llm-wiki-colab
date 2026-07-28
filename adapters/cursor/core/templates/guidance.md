## Memory boundary

This project uses two persistent memory layers; mis-allocation drops content into ambiguity.

- **Your agent/user memory holds**: user identity, preferences, workflow style, cross-project guidance. Persists across all sessions for *this user*, regardless of project.
- **The wiki (`.llm-wiki/`) holds**: project-specific knowledge, syntheses, decisions, experiment results. Persists across all sessions for *this project*, regardless of user.

When a fact emerges and the destination is unclear, ask: does it follow the user across projects, or does it stay with the project across users? User-shaped goes to your user memory; project-shaped goes to the wiki. If both, file the project-shaped half to the wiki.

## Wiki maintenance behavior

The wiki is this project's durable memory. Read it to recall context; write to it to remember. Apply this in both directions, proactively, without waiting to be asked.

- **Read** the wiki when project context would help an answer. The index (page catalog) and the last 5 log entries are injected into your context at session start, so you already hold the wiki's current state, there is no need to re-open the index file to see what exists or what changed; drill into named `.llm-wiki/` page files for their bodies. Cite page names when synthesizing. If a wiki claim conflicts with current code or results, trust what is observed now and flag the stale page rather than repeating it.
- **Write** to the wiki whenever significant work produces something a future session would benefit from: experiment results (config, metrics, what changed, what surprised), decisions with stated reasons, reusable syntheses, contradictions of prior claims. Follow the Ingest procedure in the wiki's `SCHEMA` file.

**Finish the cycle: every wiki edit ends with a commit** in `.llm-wiki/`, which is its own git repo with its own remote:

```bash
git -C .llm-wiki add <files-by-name>
git -C .llm-wiki commit -m "<message>"
```

Run these without asking; local commits are reversible. Before committing, run the **Verification Gate** (`core/agents/verification-gate.md` in the llm-wiki plugin) over every page created or edited: it catches projection-as-fact, missing corpus tags on numerical claims, missing back-references, and missing log/index entries. Push only when explicitly asked, and when pushing follow `core/agents/wiki-write-protocol.md` (the `wiki_push` wrapper) rather than plain `git push`, so concurrent writers never collide.

Honest reporting: bad results and contradicted claims get filed truthfully, not polished; never report metrics from projections, only from real outputs. See `core/agents/discipline-gates.md` for the "Universal Rationalizations (Always Wrong)" table.

Slash commands: `/wiki-init` (attach or create the wiki), `/wiki-experiment`, `/wiki-source`, `/wiki-lint`, `/wiki-doctor` (self-check). The proactive behavior above is the default; the commands exist to force an action explicitly.
