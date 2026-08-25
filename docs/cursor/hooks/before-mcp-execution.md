# beforeMCPExecution

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

Note: the reference page documents `beforeMCPExecution` and `beforeShellExecution` together under a single combined heading, "beforeShellExecution / beforeMCPExecution". This file extracts the parts specific to `beforeMCPExecution`; see `before-shell-execution.md` for the shell counterpart. Fields and notes that the page states only once for the combined pair are marked as such below.

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`beforeMCPExecution` is listed under "Control MCP tool usage", paired with `afterMCPExecution`.

Firing condition, verbatim (for the combined pair): "Called before any shell command or MCP tool is executed. Return a permission decision."

No hook-specific skip condition beyond the general cloud-agent caveats below is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `beforeMCPExecution` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `beforeMCPExecution` anywhere.

Cloud agents: NOT supported.
`beforeMCPExecution` does not appear in the "Supported hooks" table.
It is listed in the "Hooks not available in cloud agents" table with this reason, verbatim: "beforeMCPExecution / afterMCPExecution: Deferred while cloud agents can still start in a read-only environment, where hooks don't load and MCP hook timing is unclear."

## Input schema

```json
// beforeMCPExecution input
{
  "tool_name": "<tool name>",
  "tool_input": "<json params>",
  "mcp_server_name": "<server name from mcp.json>"
}
// Plus either (HTTP/SSE servers):
{ "url": "<server url>", "mcp_server_url": "<server url>" }
// Or (stdio servers):
{ "command": "<launch command and args>" }
```

`beforeMCPExecution` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

The page's field table for this combined section:

| Field           | Type   | Description                                                                                          |
|-----------------|--------|----------------------------------------------------------------------------------------------------------|
| tool_name       | string | Name of the MCP tool about to run                                                                        |
| tool_input      | string | JSON params string that will be passed to the tool                                                       |
| mcp_server_name | string | The server's key in its mcp.json (for example, "linear"). Use this to recognize a specific server.       |
| mcp_server_url  | string | Server URL, present only for HTTP/SSE servers                                                            |
| url             | string | Same as mcp_server_url; present only for HTTP/SSE servers                                                |
| command         | string | The stdio launch command and arguments joined with spaces; present only for stdio servers                |

The page adds this guidance, verbatim: "Match on `mcp_server_name` (and `tool_name`) to decide whether a call targets your server. `command` is the launch string from the server's config and can differ between installs: relative paths, `$${CURSOR_PLUGIN_ROOT}` expansion, or an HTTP transport (which has no `command` at all). A hook that allows anything it does not recognize should treat a missing or unexpected `mcp_server_name` as a deny."

## Output schema

```json
// Output
{
  "permission": "allow" | "deny" | "ask",
  "user_message": "<message shown in client>",
  "agent_message": "<message sent to agent>"
}
```

This output schema is documented once, shared between `beforeShellExecution` and `beforeMCPExecution`, with no separate field table split by hook.

| Output Field  | Type              | Description                |
|---------------|-------------------|------------------------------|
| permission    | string            | "allow" \| "deny" \| "ask"   |
| user_message  | string (optional) | Message shown to the user     |
| agent_message | string (optional) | Message sent to the agent      |

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

The combined section's note on failure handling, verbatim: "By default, hook failures (crash, timeout, invalid JSON) allow the action through (fail-open). Set `failClosed: true` on the hook definition to block the action on failure instead. This is recommended for security-critical `beforeMCPExecution` hooks." This recommendation is stated specifically for `beforeMCPExecution`.

The agent loop waits on this hook for a permission decision before the MCP tool call runs (implied by the "Return a permission decision" firing description and the exit-code/permission blocking semantics; the page does not use the word "waits" or "synchronous" explicitly).

## Matcher support

Not documented. The "Available matchers by hook" list on the page covers `preToolUse`/`postToolUse`/`postToolUseFailure`, `subagentStart`/`subagentStop`, `beforeShellExecution`/`afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `stop`, `afterAgentResponse`, and `afterAgentThought`, but does not include an entry for `beforeMCPExecution`.
The combined heading's own generic `matcher` per-script option ("Filter criteria for when hook runs") applies, and the input fields (`tool_name`, `mcp_server_name`, etc.) suggest what a matcher would plausibly target, but the page states no matcher-field mapping for this event specifically.

## Other reference details

- Cloud agents: this hook is explicitly excluded from cloud execution (see Surface availability above), unlike most other agent hooks.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `beforeMCPExecution`.
- No redaction feature is documented for `beforeMCPExecution` specifically.
- No other known limitations are stated for `beforeMCPExecution` beyond its cloud-agent exclusion.
