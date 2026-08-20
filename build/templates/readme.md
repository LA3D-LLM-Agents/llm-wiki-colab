# llm-wiki-colab

This branch is generated build output.
Development happens on the `src` branch.

## Install

### Claude Code

```
/plugin marketplace add {{owner_repo}}
/plugin install llm-wiki@llm-wiki-colab
```

### Codex

```
codex plugin marketplace add {{owner_repo}}
codex plugin add llm-wiki@llm-wiki-colab
```

Codex requires a restart after a plugin change.
The plugin's SessionStart and PostToolUse hooks are trust-gated on Codex: they are discovered but do not run until you approve them in the interactive TUI's startup hooks review.
`codex exec` has no review flow, so a headless Codex session gets the plugin's skills but none of its hooks, and therefore no session-start wiki orientation.
Codex updates are keyed on the plugin's manifest version, not on the commit, so a release only reaches Codex users when that version is bumped.

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

Version {{version}}, built from src commit {{source_ref}}.
