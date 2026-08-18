# llm-wiki-colab

Source tree for the llm-wiki plugin marketplace.
Consumers install from `main`, which is generated build output.
See [docs/repository-model.md](docs/repository-model.md).

The plugin gives a repo opt-in, durable memory backed by the repo's GitHub wiki, cloned into a gitignored `.llm-wiki/` folder.

It packages the [llm-wiki](https://github.com/tobi/llm-wiki) durable-memory pattern, ported from [`crcresearch/llm-wiki-memory-template`](https://github.com/crcresearch/llm-wiki-memory-template).
The pattern is described in [Beyond Memory](https://doi.org/10.5281/zenodo.21213175) (Saboia Moreira et al., 2026, Zenodo).
A machine-readable [`CITATION.cff`](CITATION.cff) is in the repo, so GitHub shows a "Cite this repository" button.

## Layout

| Path                | Contents                                               |
| ------------------- | ------------------------------------------------------ |
| `plugins/llm-wiki/` | the plugin source                                      |
| `build/`            | assembly tooling and templates                         |
| `tests/`            | behavior tests run against build output                |
| `docs/`             | repository model, development practices, plugin design |

## Development

See [docs/development.md](docs/development.md).
devenv.sh provisions the toolchain for those who use it.
