# postToolUseFailure

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`postToolUseFailure` is listed under "Generic tool use hooks (fires for all tools)", grouped with `preToolUse` and `postToolUse`.

Firing condition, verbatim: "Called when a tool fails, times out, or is denied. Useful for error tracking and recovery logic."

This is the counterpart to `postToolUse`: `postToolUse` fires only on successful tool execution, while `postToolUseFailure` fires on failure, timeout, or denial. No further hook-specific skip condition is documented beyond the general cloud-agent caveat below.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `postToolUseFailure` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `postToolUseFailure` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `postToolUseFailure` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// Input
{
  "tool_name": "Shell",
  "tool_input": { "command": "npm test" },
  "tool_use_id": "abc123",
  "cwd": "/project",
  "error_message": "Command timed out after 30s",
  "failure_type": "timeout" | "error" | "permission_denied",
  "duration": 5000,
  "is_interrupt": false
}
```

`postToolUseFailure` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

| Field         | Type    | Description                                                                    |
|---------------|---------|------------------------------------------------------------------------------------|
| tool_name     | string  | Not documented (JSON example shows the tool type, e.g. "Shell")                    |
| tool_input    | object  | Not documented (JSON example shows tool-specific parameters, e.g. { command })     |
| tool_use_id   | string  | Not documented (JSON example shows a unique identifier, e.g. "abc123")             |
| cwd           | string  | Not documented (JSON example shows the working directory, e.g. "/project")         |
| error_message | string  | Description of the failure                                                         |
| failure_type  | string  | Type of failure: "error", "timeout", or "permission_denied"                        |
| duration      | number  | Time in milliseconds until the failure occurred                                    |
| is_interrupt  | boolean | Whether this failure was caused by a user interrupt/cancellation                   |

## Output schema

```json
// Output
{
  // No output fields currently supported
}
```

The page states explicitly: "No output fields currently supported." There is no output field table for this hook.

## Blocking behavior

`postToolUseFailure` is observational: the failure, timeout, or denial has already happened by the time the hook runs, and it has no output fields to change or block anything.

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

Because the hook has no `permission` output field and fires after the outcome is already determined, the page gives no indication that exit code `2` has any effect for `postToolUseFailure`; this is not documented for this hook specifically.

`failClosed` (general per-script option): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`. No `postToolUseFailure`-specific note is given.

## Matcher support

Verbatim: "preToolUse / postToolUse / postToolUseFailure: Filter by tool type. Values include `Shell`, `Read`, `Write`, `Grep`, `Delete`, `Task`, and MCP tools using the `MCP:<tool_name>` format."

## Other reference details

- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `postToolUseFailure`.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- No redaction feature is documented for `postToolUseFailure` specifically.
- No known limitations are stated for `postToolUseFailure` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
