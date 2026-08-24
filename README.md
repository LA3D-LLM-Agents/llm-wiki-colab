# llm-wiki-colab

This branch is generated build output.
Development happens on the `src` branch.

## Install

### Claude Code

```
/plugin marketplace add LA3D-LLM-Agents/llm-wiki-colab
/plugin install llm-wiki@llm-wiki-colab
```

### Codex

```
codex plugin marketplace add LA3D-LLM-Agents/llm-wiki-colab
codex plugin add llm-wiki@llm-wiki-colab
```

Codex requires a restart after a plugin change.
The plugin's SessionStart and PostToolUse hooks are trust-gated on Codex: they are discovered but do not run until you approve them in the interactive TUI's startup hooks review.
`codex exec` has no review flow, so a headless Codex session gets the plugin's skills but none of its hooks, and therefore no session-start wiki orientation.
Codex updates are keyed on the plugin's manifest version, not on the commit, so a release only reaches Codex users when that version is bumped.

## Update

### Claude Code

```
claude plugin marketplace update llm-wiki-colab
claude plugin update llm-wiki@llm-wiki-colab
```

Pass the full `llm-wiki@llm-wiki-colab` form; `update` does not resolve the bare plugin name.
A restart applies the update.

### Codex

```
codex plugin marketplace upgrade
codex plugin add llm-wiki@llm-wiki-colab
```

There is no plugin-level update command; re-running `add` after the marketplace upgrade replaces the install at the new version.

## Uninstall

### Claude Code

```
/plugin uninstall llm-wiki@llm-wiki-colab
/plugin marketplace remove llm-wiki-colab
```

### Codex

```
codex plugin remove llm-wiki@llm-wiki-colab
codex plugin marketplace remove llm-wiki-colab
```

## How to cite

If you use this plugin, please cite the paper it implements.

> Saboia Moreira, P., Vardeman II, C., Sweet, J., & Sweet, C. (2026). *Beyond Memory: A Templated Substrate for Heterogeneous Collaborative Knowledge Work with LLM Agents*. Zenodo. https://doi.org/10.5281/zenodo.21213175

A machine-readable `CITATION.cff` is included in the source repository.

## Provenance

Version 0.2.0, built from src commit 0a9e852be5a4a43ed901a9724f13052dcce1b91e.
