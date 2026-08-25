# afterFileEdit

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`afterFileEdit` is listed under "Control file access and edits", paired with `beforeReadFile`.

Firing condition, verbatim: "Fires after the Agent edits a file; useful for formatters or accounting of agent-written code."

No hook-specific skip condition beyond the general cloud-agent caveat below is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `afterFileEdit` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `afterFileEdit` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `afterFileEdit` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// Input
{
  "file_path": "<absolute path>",
  "edits": [{ "old_string": "<search>", "new_string": "<replace>" }]
}
```

`afterFileEdit` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

The page gives no dedicated field table for `afterFileEdit`, only the JSON example above.

| Field              | Type   | Description                                                                                       |
|--------------------|--------|--------------------------------------------------------------------------------------------------------|
| file_path          | string | Not documented (JSON example shows the absolute path to the edited file)                               |
| edits              | array  | Not documented as a whole; each entry has old_string and new_string (see field breakdown below)        |
| edits[].old_string | string | Not documented (JSON example shows the search text)                                                    |
| edits[].new_string | string | Not documented (JSON example shows the replacement text)                                               |

Compare with `afterTabFileEdit`, whose page section states it "Includes detailed edit information: `range`, `old_line`, and `new_line` for precise edit tracking" as a key difference from `afterFileEdit`, implying `afterFileEdit`'s edits do not carry those three fields.

## Output schema

Not documented. The page shows no output JSON example and no output field table for `afterFileEdit`. It is a post-edit hook intended for formatters or accounting, with no documented permission or content-modification outputs.

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

Since the edit has already been applied by the time this hook fires and no output schema is documented, the page gives no indication that exit code `2` has any effect for `afterFileEdit`; this is not documented for this hook specifically.

`failClosed` (general per-script option): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`. No `afterFileEdit`-specific note is given.

## Matcher support

Verbatim: "afterFileEdit: Filter by tool type (`TabWrite`, `Write`, etc.)."

## Other reference details

- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `afterFileEdit`.
- No redaction feature is documented for `afterFileEdit` specifically.
- Quickstart example on the page uses this hook for formatting: `{ "hooks": { "afterFileEdit": [{ "command": "./hooks/format.sh" }] } }`.
- No other known limitations are stated for `afterFileEdit` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
