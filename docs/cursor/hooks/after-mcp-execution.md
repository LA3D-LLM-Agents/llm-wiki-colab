# afterMCPExecution

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`afterMCPExecution` is listed under "Control MCP tool usage", paired with `beforeMCPExecution`.

Firing condition, verbatim: "Fires after an MCP tool executes; includes the tool's input parameters and full JSON result."

No hook-specific skip condition beyond the general cloud-agent caveats below is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `afterMCPExecution` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `afterMCPExecution` anywhere.

Cloud agents: NOT supported.
`afterMCPExecution` does not appear in the "Supported hooks" table.
It is listed in the "Hooks not available in cloud agents" table with this reason, verbatim: "beforeMCPExecution / afterMCPExecution: Deferred while cloud agents can still start in a read-only environment, where hooks don't load and MCP hook timing is unclear."

## Input schema

```json
// Input
{
  "tool_name": "<tool name>",
  "tool_input": "<json params>",
  "mcp_server_name": "<server name from mcp.json>",
  "result_json": "<tool result json>",
  "duration": 1234
}
```

`afterMCPExecution` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

| Field           | Type   | Description                                                                            |
|-----------------|--------|-----------------------------------------------------------------------------------------|
| tool_name       | string | Name of the MCP tool that was executed                                                  |
| tool_input      | string | JSON params string passed to the tool                                                   |
| mcp_server_name | string | The server's key in its mcp.json                                                        |
| mcp_server_url  | string | Server URL, present only for HTTP/SSE servers                                           |
| result_json     | string | JSON string of the tool response                                                        |
| duration        | number | Duration in milliseconds spent executing the MCP tool (excludes approval wait time)     |

Note: `mcp_server_url` is listed in the page's field table for this hook even though it does not appear in the JSON example above; the JSON example is illustrative, not exhaustive.

## Output schema

Not documented. The page shows no output JSON example and no output field table for `afterMCPExecution`. It is an observational, post-execution hook with no documented permission or content-modification outputs.

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

Since the MCP tool call has already executed by the time this hook fires and no output schema is documented, the page gives no indication that exit code `2` has any effect for `afterMCPExecution`; this is not documented for this hook specifically.

`failClosed` (general per-script option): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`. No `afterMCPExecution`-specific note is given.

## Matcher support

Not documented. The "Available matchers by hook" list on the page covers `preToolUse`/`postToolUse`/`postToolUseFailure`, `subagentStart`/`subagentStop`, `beforeShellExecution`/`afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `stop`, `afterAgentResponse`, and `afterAgentThought`, but does not include an entry for `afterMCPExecution`.

## Other reference details

- Cloud agents: this hook is explicitly excluded from cloud execution (see Surface availability above), unlike most other agent hooks.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `afterMCPExecution`.
- No redaction feature is documented for `afterMCPExecution` specifically.
- The example configuration on the page shows `afterMCPExecution` with only a `command`, no `matcher`: `{ "hooks": { "afterMCPExecution": [{ "command": "./script.sh" }] } }`.
- No other known limitations are stated for `afterMCPExecution` beyond its cloud-agent exclusion.
