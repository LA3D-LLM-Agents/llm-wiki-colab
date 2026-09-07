# Harness capability probes

Run these Python tests independently of the Bash suite:

```sh
uv run --with pytest python -B -m pytest tests/harness
```

By default this runs offline audit checks and Codex's local metadata inspection.
Tests that make model calls are skipped unless `--run-live` is supplied. Selecting
`-m live` alone does not authorize model calls. Missing CLIs or wrapper credentials
also produce explicit skips. Pytest exit codes apply: an all-skipped run exits 0,
so check the skip summary when verifying a harness.

```sh
# Offline only; no harness CLIs or credentials needed
uv run --with pytest python -B -m pytest tests/harness -m 'not capability'

# All capabilities across all three harnesses, retaining private evidence
uv run --with pytest python -B -m pytest tests/harness --run-live --keep -s

# One capability and harness
uv run --with pytest python -B -m pytest tests/harness/test_skill_body.py --run-live --harness codex

# Override the model for a single harness
uv run --with pytest python -B -m pytest tests/harness --run-live --harness claude --model haiku

# List cases without executing them
uv run --with pytest python -B -m pytest tests/harness --collect-only
```

Each capability/harness pair is one test with its own negative and positive
controls. Controls use separate harness state roots, and do not depend on other
tests running first. Claude defaults to `haiku`, Codex's live sessions to
`gpt-5.6-luna`, and Cursor to its harness default. `--model` requires a specific
`--harness`; Codex's local prompt inspection does not use a model.

## Capabilities

`test_skill_metadata.py` checks that a random skill name and description marker
are absent without the plugin and present after loading it. Codex renders its
model-visible prompt locally. Claude and Cursor each spend two sessions reporting
metadata, with conversation audits rejecting any tool use. Tools remain registered
because removing Claude's Skill tool can also remove its metadata. The skill-body
marker must not appear in either response.

`test_skill_body.py` spends two live sessions per harness, including Codex. Both
cases install the same named skill and description. The first body has no marker;
only after that control completes is the positive body token written. The prompt
says `Load the skill {name}` using the bare name, then asks for the marker, without
prescribing a file path or loading mechanism. Both cases require incoming body
text, and the positive case also requires token recovery. An assistant echo alone
or a control that never loaded the skill fails.

These minimal fixture plugins establish harness capabilities, not built-artifact
wiring. Body reads and skill invocations are allowed in the body probe. Neither
probe evaluates automatic skill selection, instruction compliance, or execution
of bundled resources.

## Evidence and isolation

The probes use `scripts/isolated-<harness>.sh` and clean `/tmp` workspaces. Wrappers
require credentials even for local Codex inspection. Codex live sessions retain
its read-only sandbox; when launched inside another sandbox, nested sandbox
initialization can fail before a file read. Report this as a failure rather than
silently weakening the sandbox or retrying with different permissions.

`--keep` retains raw captures and per-test `results.json`, including the version,
model selection, last phase, case audits, and failure reason. Use `-s` to see paths
for successful tests. Captures may contain identity, account context, and raw API
bodies; keep them private. Without `--keep`, captures are deleted after each test,
including failures. Wrappers remove credential copies after each command; forced
termination can leave scratch data behind.

## Code layout

- `conftest.py`: pytest options, model-call gate, and run lifecycle fixture.
- `harness_support.py`: native fixture plugins and isolated CLI execution.
- `conversation.py`: harness-specific parsers validate raw records and return a
  `Conversation` containing `TextMessage`, `ToolCall`, and `ToolResult` dataclasses.
- `skill_assertions.py`: metadata and body evidence requirements.
- `test_skill_metadata.py`, `test_skill_body.py`: explicit capability sequences.
- `test_conversation.py`, `test_skill_*_audit.py`: offline parser and assertion tests.

The existing `cursor/test_session_context.sh` and isolation canaries under
`scripts/isolated-*.test.sh` remain separately invoked shell probes.
