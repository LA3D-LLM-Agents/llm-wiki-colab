# Development

## Toolchain

devenv.sh provisions the stable tools used for local work: `jq`, `shellcheck`, and `uv`.
devenv is a convenience, not a contract.
Every build, test, and publish script is a plain script runnable with those tools on PATH, and nothing in the repository may require the devenv shell.

Platform CLIs (`claude`, and later `codex` and `cursor`) are installed at their current release, outside the devenv lock.
They are the subject under test, so they must match what users actually run rather than a pinned version.

## Build and test discipline

Always build to a scratch directory and test or install the built artifact from there.
Never point a plugin host at the source tree.
Claude's `--plugin-dir` flag can bypass this and load the source tree directly; that is fine as a deliberate, occasional act, but it is not the supported development loop.

## Script language conventions

Build and publish tooling is Python, run as uv single-file scripts using PEP 723 inline metadata.
Behavior tests are plain bash.

## Template hydration

Artifact-tree templates under `build/templates/` use `{{token}}` placeholders.
The build fails if any token survives unhydrated into output.

## CI and evaluation boundaries

CI runs only deterministic gates: build, validation, and behavior tests.
CI never gates on model-based evaluation.
Evaluation runs are operator-driven, since subscription auth is not reliably available in CI, and their results land as data rather than as a pass/fail signal.
