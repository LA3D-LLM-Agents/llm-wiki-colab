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
uv run --with pytest python -B -m pytest tests/harness -m 'not capability and not integration'

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

`test_session_context.py` tests SessionStart delivery with two sessions per
harness. Both run a fixture hook that generates a fresh token and captures its
input payload. The silent control emits no context; the positive control emits
the token using the harness's native context field. The test requires hook
execution, token recovery, incoming context evidence, and no model tool use.
This distinguishes a hook that runs from context that actually reaches the model.

```sh
uv run --with pytest python -B -m pytest tests/harness/test_session_context.py --run-live --keep -s
```

Claude's transcript can omit injected SessionStart context, so its delivery
assertion uses the wrapper's API request capture. Its transcript still supplies
the tool-use audit. Codex and Cursor use their conversation records. Missing
evidence fails; an assistant echo alone cannot satisfy the positive case.

Codex's delivery pair explicitly uses `--dangerously-bypass-hook-trust` for the
generated fixture hook. A separate third session tests fresh default-trust state:
the hook must not execute and no token may reach the model. Results record the
trust mode; the bypassed pass does not establish ordinary headless delivery.
These tests cover startup context, not resume/compaction events, user-visible
banners, or the built llm-wiki orientation hook.

`test_post_write.py` tests advisory delivery after Claude `Write` and `Edit`,
Codex `apply_patch`, and Cursor `Write`. Each case performs two scratch writes:
one with a silent post-tool hook and one with an emitting hook. The hook captures
its input and reads the target before generating a fresh advisory token. Both
controls require the matching tool event, the intended target, and completed
file contents observed by the hook. The positive control also requires incoming
advisory context and token recovery; the token never goes in the written file.

```sh
uv run --with pytest python -B -m pytest tests/harness/test_post_write.py --run-live --keep -s
```

These probes explicitly enable scratch-file writes: Claude accepts edits, Codex
uses `workspace-write` and explicit fixture-hook trust, and Cursor uses `--force`.
The other probes retain their existing modes. Target reads are permitted for
edit prerequisites; calls that do not reference the target or that contain an
advisory token fail the audit. Hook execution without delivery and assistant-only
token echoes also fail. Claude uses API request captures for incoming context.

The fixture emits structured `PostToolUse.additionalContext` on Claude/Codex and
[`postToolUse.additional_context`](https://cursor.com/docs/hooks#posttooluse) on
Cursor. This establishes harness capability, not the behavior of llm-wiki's
current plain-stdout advisory. Cursor's `afterFileEdit` and actual plugin wiring
remain separate questions. No assertion requires the model to follow the advice.

## Built-plugin integration

`test_plugin_orientation.py` is marked `integration` and `live`. It assembles the
plugin into scratch space and installs the appropriate subtree without modifying
the artifact or substituting fixture hooks. Claude and Codex use a local
marketplace; Cursor gets a copy under the isolated home's
`.cursor/plugins/local/llm-wiki`. No `--plugin-dir` override is used. Two fresh
sessions per harness compare an unopted-in project with a locally seeded
`.llm-wiki` repository.

```sh
uv run --with pytest python -B -m pytest tests/harness/test_plugin_orientation.py \
  --run-live --keep -s
```

The context capture and model response must contain the unique index marker and
the latest five of seven log markers. The request must also contain the shipped
memory guidance and the correctly namespaced SCHEMA reference. Older log entries,
page bodies, and SCHEMA contents must stay out of the injected context. The
unopted project must receive no seeded state or memory guidance. Transcript tool
audits exclude file reads as another route to the markers. Claude uses its API
request capture for context evidence; Codex and Cursor use conversation records.
Codex runs with explicit hook-trust bypass, recorded in the results. Default-trust
behavior remains covered separately by the synthetic SessionStart probe.

This tests installed-plugin orientation delivery, not the separate question of
whether orientation changes behavior. It does not test the user-visible banner,
wiki fetching, remote marketplace publishing, or Cursor account-side installation.

## Non-deterministic resource evaluation

`test_resource_resolution.py` is marked `non_deterministic` as well as `live`.
It requires `--run-live --run-non-deterministic`, a single `--harness`, and an
explicit `--model`. It is not part of ordinary capability runs or CI gates.

```sh
uv run --with pytest python -B -m pytest tests/harness/test_resource_resolution.py \
  --run-live --run-non-deterministic --harness codex --model gpt-5.6-luna \
  --resource-samples 5 -s
```

Each sample is independent, with fresh paths and state, and makes one model
session. No failed sample is retried automatically. The fixed scenario provides
an intended bundled Python script and a workspace-relative decoy of the same
name. The skill uses `${CLAUDE_SKILL_DIR}` for Claude and `$SKILL_DIRECTORY` for
Codex/Cursor. The user prompt names the skill and operation, without explaining
path resolution. The execution contract requires the intended script, exact
arguments, and the project working directory.

Python launch monitors record attempts before the interpreter opens the script;
scripts separately record their identity, path, arguments, cwd, and launch ID.
Thus a failed launch without a receipt cannot disappear when the model recovers.
The trace auditor requires simple `python`/`python3` commands and matching launch
counts. Absolute interpreters, compound commands, computed command strings, and
unrecognized execution forms are unassessable infrastructure/evidence failures,
not first-attempt successes. This intentionally narrow scenario is not a test of
every possible execution strategy.

Outcomes are `first_attempt_success`, `recovered`, `incorrect_execution`,
`no_execution`, and `infrastructure_failure`. Only first-attempt success passes
the pytest assertion. Recovery remains a failed sample. The terminal summary
reports counts and the success fraction excluding infrastructure failures; it
does not establish reliability from a single sample. Missing prerequisites are
pytest skips and do not count as assessed samples.

All evaluation captures are retained automatically, including failed samples.
An aggregate `summary.json` links each attempt to its captures. Harness version
and explicit model selector are recorded; selectors/aliases can still move, so
these results do not claim an immutable resolved model version. Keep scenarios
and selectors consistent for comparisons, and retain the private captures.

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
- `session_context.py`: generated session hooks and delivery evidence requirements.
- `post_write.py`: generated post-tool hooks and completed-write delivery evidence.
- `test_skill_metadata.py`, `test_skill_body.py`: explicit capability sequences.
- `test_session_context.py`: SessionStart delivery and Codex default-trust cases.
- `test_post_write.py`: native file-write tools and post-tool advisory delivery.
- `test_conversation.py`, `test_skill_*_audit.py`: offline parser and assertion tests.
- `test_session_context_audit.py`: offline context delivery controls.
- `test_post_write_audit.py`: offline write/target binding and advisory controls.
- `plugin_orientation.py`, `test_plugin_orientation.py`: seeded wiki and built-plugin
  orientation integration across the three harnesses.
- `test_plugin_orientation_audit.py`: offline orientation contract checks.
- `resource_resolution.py`, `test_resource_resolution.py`: instrumented resource
  evaluation and model/harness samples.
- `test_resource_resolution_audit.py`: offline launch-monitor and classifier checks.

The older `cursor/test_session_context.sh` remains separately invocable; the
pytest suite now covers that delivery capability with an added silent control.
Isolation canaries under `scripts/isolated-*.test.sh` remain separate shell probes.
