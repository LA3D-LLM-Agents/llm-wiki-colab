# Cut a release: reading a failed live check

Read the section that matches the command that failed.
Every path here stays on this machine; captures hold private session content and are never attached to an issue or a release.

## The pytest run

### Finding the failing case

The `-ra` short summary at the end lists each failure by test id, and each capture directory is printed on its own line right after the result character of the case it belongs to:

```text
tests/harness/test_plugin_advisory.py .Private captures retained: /tmp/skill-capability-ow25a36r
FPrivate captures retained: /tmp/skill-capability-dyu2ho63
```

The `F` and the line following it belong together.
Retained captures accumulate across runs, so when the terminal output is gone, list today's by time and read the status of each:

```sh
for d in /tmp/skill-capability-*/; do
    [ -f "$d/results.json" ] || continue
    printf '%s  ' "$(stat -c %y "$d" | cut -c1-16)"
    jq -r '[.harness, .phase, .status, (.failure // "-")] | join("  ")' "$d/results.json"
done | sort | tail -20
```

### What a capture holds

| Path                    | Content                                                                                           |
| :---------------------- | :------------------------------------------------------------------------------------------------ |
| `results.json`          | Harness, model, phase, `status`, and `failure`, the one-line reason pytest raised.                 |
| `<phase>.stdout`        | What the harness printed to the operator: the model's final reply for `-p` style runs.            |
| `<phase>.stderr`        | The CLI's own errors: authentication, sandbox, missing binary, rate limits.                        |
| `<phase>/`              | The isolated home the CLI ran in, including its session transcripts and any plugin it installed.  |
| `workspace/`            | The repository the agent saw, with any files it wrote.                                            |
| `built/` and `build.log`| The assembled artifact under test and the build output.                                           |
| `version.stdout`        | The harness version the case ran against.                                                         |

Start with `failure` in `results.json`, then the phase it names.
Read `<phase>.stderr` first; a non-empty stderr almost always explains a `exited 1` failure by itself.
Read `<phase>.stdout` when the failure is about content: a marker not quoted back, a skill not listed, an advisory not echoed.

### Telling the cause apart

| `failure` or stderr says                                | Meaning                                                                        | Move                                                                                                       |
| :------------------------------------------------------ | :----------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------- |
| `Authentication required`, `access token could not be refreshed`, `Not logged in` | The harness sign-in lapsed between the check and the case. | Ask the operator to sign in again, rerun `scripts/check-harness-auth.sh`, restart the live checks.        |
| `exited 1; see <phase>.stderr` with a sandbox or landlock message | Codex could not initialize its sandbox inside this session's sandbox. | Rerun with the tool sandbox off, as step 3 says.                                                          |
| `wrapper credentials missing` or `missing from PATH` as a skip | The harness was never exercised.                                     | Install or sign in, then rerun; a run that skipped a harness does not count.                               |
| `marker missing`, `not listed`, `advisory_received: false` with an ordinary reply in stdout | Context did not reach the model, or the model ignored the prompt's format. | Read the reply. If the marker is absent from the isolated home too, the plugin did not load: a real regression. If the reply shows the model saw it and answered freely, rerun that one case alone (below) and report both outcomes to the operator. |
| Empty stdout, empty stderr, `exited 124`                | The harness hung or timed out.                                                 | Rerun that case alone; if it repeats, the harness version is the suspect, not the plugin.                  |

### Rerunning one case

Narrow to the harness and test id from the short summary so the rerun spends calls on that case only:

```sh
uv run --with pytest python -B -m pytest tests/harness/<file>.py --run-live --keep -s -ra --harness <claude|codex|cursor> -k '<test name>'
```

A passing rerun is evidence for the operator's decision, not a substitute for it; the skill's rule stands that a failing case blocks the release until it is understood.

## The bash run with the Cursor smoke

The smoke section of `tests/test_cursor_manifests.sh` makes two Cursor calls against the real account and prints its evidence inline.
When any assertion in a group fails, the group's raw output follows it:

- `smoke reply (cursor-agent stdout+stderr):` is the model's two-line answer or the CLI's error for the first call.
- `probe shell call` is the shell tool record the second call produced, `probe trace tail` the last lines of its stream-json when no record was found, and `probe stderr` the CLI's own error for that call.

A reply that is a CLI error line explains every FAIL in the group at once.
A reply that lists skills but omits the marker means the plugin installed but sessionStart context did not reach the model.
A reply that is `NONE` on both lines means the plugin did not install; check `~/.cursor/plugins/local/llmwiki-smoke` was written and that no `llm-wiki` install was left behind from an interrupted earlier run (the smoke stashes it at `.llmwiki-smoke-stash` and moves it back on exit).

Any FAIL line outside the smoke section is a deterministic failure that CI would also have caught; read it as an ordinary test failure.
