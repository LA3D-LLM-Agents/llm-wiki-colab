# postToolUse

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`postToolUse` is listed under "Generic tool use hooks (fires for all tools)", grouped with `preToolUse` and `postToolUseFailure`.

Firing condition, verbatim: "Called after successful tool execution. Useful for auditing, analytics, and injecting context."

No hook-specific skip condition is documented for `postToolUse` beyond the general cloud-agent caveat below. Note the word "successful" in the firing condition: a failed, timed-out, or denied tool call fires `postToolUseFailure` instead (see that hook's file).

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `postToolUse` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `postToolUse` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `postToolUse` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// Input
{
  "tool_name": "Shell",
  "tool_input": { "command": "npm test" },
  "tool_output": "{\"exitCode\":0,\"stdout\":\"All tests passed\"}",
  "tool_use_id": "abc123",
  "cwd": "/project",
  "duration": 5432,
  "model": "claude-opus-4-7-thinking-max",
  "model_id": "claude-opus-4-7",
  "model_params": [
    { "id": "thinking", "value": "true" },
    { "id": "context", "value": "1m" },
    { "id": "effort", "value": "max" }
  ]
}
```

`postToolUse` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

| Field       | Type   | Description                                                                     |
|-------------|--------|-----------------------------------------------------------------------------------|
| tool_name   | string | Not documented (JSON example shows the tool type, e.g. "Shell")                   |
| tool_input  | object | Not documented (JSON example shows tool-specific parameters, e.g. { command })    |
| tool_output | string | JSON-stringified result payload from the tool (not raw terminal text)             |
| tool_use_id | string | Not documented (JSON example shows a unique identifier, e.g. "abc123")            |
| cwd         | string | Not documented (JSON example shows the working directory, e.g. "/project")        |
| duration    | number | Execution time in milliseconds                                                    |

## Output schema

```json
// Output
{
  "updated_mcp_tool_output": { "modified": "output" },
  "additional_context": "Test coverage report attached."
}
```

| Output Field             | Type               | Description                                                          |
|--------------------------|--------------------|--------------------------------------------------------------------------|
| updated_mcp_tool_output  | object (optional)  | For MCP tools only: replaces the tool output seen by the model           |
| additional_context       | string (optional)  | Extra context injected into the conversation after the tool result       |

## Blocking behavior

`postToolUse` fires after the tool has already executed successfully, so it does not carry a `permission`/allow-deny gate in its output schema (unlike `preToolUse`); its only documented outputs modify what the model sees afterward (`updated_mcp_tool_output`, `additional_context`).

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

The page does not state whether exit code `2` has any effect for `postToolUse` specifically, since the tool has already run and there is no documented `permission` field for this hook; treat this as not documented for `postToolUse`.

`failClosed` (general per-script option): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`. No `postToolUse`-specific note is given.

## Matcher support

Verbatim: "preToolUse / postToolUse / postToolUseFailure: Filter by tool type. Values include `Shell`, `Read`, `Write`, `Grep`, `Delete`, `Task`, and MCP tools using the `MCP:<tool_name>` format."

Example configuration shown on the page:

```json
{
  "hooks": {
    "postToolUse": [{ "command": "./hooks/audit-tool.sh" }]
  }
}
```

## Other reference details

- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `postToolUse`.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- No redaction feature is documented for `postToolUse` specifically.
- No known limitations are stated for `postToolUse` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
