---
description: Register this repo as a federation agent (publish an agent Card, add the discovery topic).
---

Run the enrollment helper and relay its interactive output:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/core/scripts/agent-comms/enroll.sh"
```

It idempotently generates `.llm-wiki/Card_<agent>.md` from prompts (description, topics, capabilities) and, for repos outside the `LA3D-LLM-Agents` org, offers to add the `nd-llm-wiki` GitHub topic so the federation index can discover this agent (subject to a trusted-owner allowlist). Pass `--dry-run` to preview without writing anything.

Requires `git` and `gh` (run `/wiki-doctor` to check). After it writes the Card, commit and push it in the wiki repo (`git -C .llm-wiki add Card_<agent>.md && git -C .llm-wiki commit && git -C .llm-wiki push`) so peers can find you. Refuses to overwrite an existing Card, edit it directly to update.
