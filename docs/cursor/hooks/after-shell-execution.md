# afterShellExecution

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`afterShellExecution` is listed under "Control shell commands", paired with `beforeShellExecution`.

Firing condition, verbatim: "Fires after a shell command executes; useful for auditing or collecting metrics from command output."

No hook-specific skip condition beyond the general cloud-agent caveat below is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `afterShellExecution` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `afterShellExecution` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `afterShellExecution` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// Input
{
  "command": "<full terminal command>",
  "output": "<full terminal output>",
  "duration": 1234,
  "sandbox": false
}
```

`afterShellExecution` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

| Field    | Type    | Description                                                                                 |
|----------|---------|-------------------------------------------------------------------------------------------------|
| command  | string  | The full terminal command that was executed                                                     |
| output   | string  | Full output captured from the terminal                                                           |
| duration | number  | Duration in milliseconds spent executing the shell command (excludes approval wait time)         |
| sandbox  | boolean | Whether the command ran in a sandboxed environment                                               |

## Output schema

Not documented. The page shows no output JSON example and no output field table for `afterShellExecution`. It is an observational, post-execution hook (auditing/metrics per its firing description) with no documented permission or content-modification outputs.

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

Since the command has already executed by the time this hook fires and no output schema is documented, the page gives no indication that exit code `2` has any effect for `afterShellExecution`; this is not documented for this hook specifically.

`failClosed` (general per-script option): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`. No `afterShellExecution`-specific note is given.

## Matcher support

Verbatim: "beforeShellExecution / afterShellExecution: Filter by the shell command text; the matcher is matched against the full command string."

## Other reference details

- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `afterShellExecution`.
- No redaction feature is documented for `afterShellExecution` specifically.
- No other known limitations are stated for `afterShellExecution` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
