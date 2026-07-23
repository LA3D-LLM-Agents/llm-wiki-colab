# llm-wiki-colab (plugins)

[![ci](https://github.com/LA3D-LLM-Agents/llm-wiki-colab/actions/workflows/ci.yml/badge.svg)](https://github.com/LA3D-LLM-Agents/llm-wiki-colab/actions/workflows/ci.yml)

Vendor plugins that package the [llm-wiki](https://github.com/tobi/llm-wiki)
durable-memory pattern as installable tooling, ported from
[`crcresearch/llm-wiki-memory-template`](https://github.com/crcresearch/llm-wiki-memory-template).

The llm-wiki pattern this plugin packages is described in [Beyond Memory](https://doi.org/10.5281/zenodo.21213175) (Saboia Moreira et al., 2026, Zenodo). Project-facing overviews: the [Wiki-Grounded Research Agent](https://la3d.github.io/WGRA) flyer, the [WGRA Nuggets](https://la3d.github.io/WGRA/blog/) blog, and the [LA3D-LLM-Agents ecosystem](https://la3d-llm-agents.github.io/).

**Status: v1 shipped (Claude Code adapter), remotely installable and test-backed.** See `BUILD-NOTES.md` for what is done and what remains. Design rationale and decisions live in the llm-wiki-vision wiki page *Plugin-Packaging-Architecture*.

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

## Requirements

- `git` (required).
- `python3` with `rdflib`, `pyshacl`, `pyyaml` (optional, only for the `core/scripts/kg` build).
- `jq`, `curl` (for `/wiki-ask`) and `gh` (for `/wiki-enroll`).

Run `/wiki-doctor` to see what is present.

## Install

```
/plugin marketplace add LA3D-LLM-Agents/llm-wiki-colab
/plugin install llm-wiki@llm-wiki-colab
/wiki-init
```

## Getting started

In a repo you want to give durable memory:

1. The wiki lives in the repo's **GitHub wiki**. If the repo has none yet, enable it (Settings -> Features -> Wikis) and create the first page, or run `/wiki-init` and follow its prompt.
2. `/wiki-init` clones/attaches the wiki into a gitignored `.llm-wiki/`.
3. Open a **new** session in that repo; the SessionStart hook injects the wiki index and recent log so the agent treats it as memory. The plugin stays silent in any repo without a `.llm-wiki/`.

## Commands

`/wiki-init` (ensure/attach), `/wiki-doctor` (self-check),
`/wiki-ask` (consult a federated agent's wiki), `/wiki-enroll` (publish this repo
to the federation), `/wiki-experiment`, `/wiki-source`, `/wiki-lint`.

## Uninstall

```
/plugin uninstall llm-wiki@llm-wiki-colab
/plugin marketplace remove llm-wiki-colab
```

## Roadmap

Deferred past v1: a **Cursor adapter** (`.cursor/rules` already exist upstream) and a **neutral MCP server** exposing the wiki operations to any MCP host. See `BUILD-NOTES.md`.

## How to cite

If you use this plugin, please cite the paper it implements:

> Saboia Moreira, P., Vardeman II, C., Sweet, J., & Sweet, C. (2026). *Beyond Memory: A Templated Substrate for Heterogeneous Collaborative Knowledge Work with LLM Agents*. Zenodo. https://doi.org/10.5281/zenodo.21213175

A machine-readable [`CITATION.cff`](CITATION.cff) is in the repo, so GitHub shows a "Cite this repository" button. The project **license is still being finalized**.
