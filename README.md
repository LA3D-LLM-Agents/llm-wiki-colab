# llm-wiki-colab (plugins)

Vendor plugins that package the [llm-wiki](https://github.com/tobi/llm-wiki)
durable-memory pattern as installable tooling, ported from
[`crcresearch/llm-wiki-memory-template`](https://github.com/crcresearch/llm-wiki-memory-template).

**Status: v1 skeleton, work in progress.** See `BUILD-NOTES.md` for what is done
and what remains. Design rationale and decisions live in the llm-wiki-vision
wiki page *Plugin-Packaging-Architecture*.

## Layout

- `core/` — neutral, vendor-agnostic: gates, `wiki-write-protocol`, `kg/`,
  `init-wiki.sh`, `lib/`, templates. Copied into each adapter at package time.
- `adapters/claude-code/` — the Claude Code plugin (`commands/`, `skills/`,
  `hooks/`, `plugin.json`). This directory is the installed plugin.
- `.claude-plugin/marketplace.json` — self-exposing marketplace
  (`source -> adapters/claude-code`).

## Model

- The plugin installs **per machine** (user scope); its SessionStart hook is
  silent unless a repo has opted in.
- **Opt-in** = the presence of a gitignored `.llm-wiki/` folder, created by
  `/wiki-init`. The memory is the repo's GitHub wiki cloned there; the project
  repo stays plain.
- Operations act only on `.llm-wiki/`, never the main repo.

## Install (once built)

```
/plugin marketplace add LA3D-LLM-Agents/llm-wiki-colab
/plugin install llm-wiki@llm-wiki-colab
/wiki-init
```

## Commands

`/wiki-init` (ensure/attach), `/wiki-doctor` (self-check), `/wiki-experiment`,
`/wiki-source`, `/wiki-lint`.
