# beforeShellExecution

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

Note: the reference page documents `beforeShellExecution` and `beforeMCPExecution` together under a single combined heading, "beforeShellExecution / beforeMCPExecution". This file extracts the parts specific to `beforeShellExecution`; see `before-mcp-execution.md` for the MCP counterpart. Fields and notes that the page states only once for the combined pair are marked as such below.

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`beforeShellExecution` is listed under "Control shell commands", paired with `afterShellExecution`.

Firing condition, verbatim (for the combined pair): "Called before any shell command or MCP tool is executed. Return a permission decision."

No hook-specific skip condition beyond the general cloud-agent caveat below is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `beforeShellExecution` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `beforeShellExecution` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `beforeShellExecution` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// beforeShellExecution input
{
  "command": "<full terminal command>",
  "cwd": "<current working directory>",
  "sandbox": false
}
```

`beforeShellExecution` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

The page's combined input field table under this heading documents only the `beforeMCPExecution`-specific fields (`tool_name`, `tool_input`, `mcp_server_name`, `mcp_server_url`, `url`, `command` as an MCP launch string); it gives no separate field table for `beforeShellExecution`'s own fields. The table below is built from the JSON example, cross-referenced against `afterShellExecution`'s documented field table where the same field name is described there.

| Field   | Type    | Description                                                                                                                                                    |
|---------|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| command | string  | Not documented for beforeShellExecution specifically (JSON example shows the full terminal command); afterShellExecution documents the same field name as "The full terminal command that was executed" |
| cwd     | string  | Not documented (JSON example shows the current working directory)                                                                                                   |
| sandbox | boolean | Not documented for beforeShellExecution specifically; afterShellExecution documents the same field name as "Whether the command ran in a sandboxed environment"     |

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

The Troubleshooting section states, verbatim: "Exit code `2` from command hooks blocks the action (equivalent to returning `permission: "deny"`). This matches Claude Code behavior for compatibility."

The combined section's note on failure handling, verbatim: "By default, hook failures (crash, timeout, invalid JSON) allow the action through (fail-open). Set `failClosed: true` on the hook definition to block the action on failure instead. This is recommended for security-critical `beforeMCPExecution` hooks." (The recommendation is stated specifically for `beforeMCPExecution`, not `beforeShellExecution`, though the fail-open default and `failClosed` mechanism apply to both.)

The agent loop waits on this hook for a permission decision before the shell command runs (implied by the "Return a permission decision" firing description and the exit-code/permission blocking semantics; the page does not use the word "waits" or "synchronous" explicitly).

## Matcher support

Verbatim: "beforeShellExecution / afterShellExecution: Filter by the shell command text; the matcher is matched against the full command string."

Example from the page:

```json
{
  "hooks": {
    "beforeShellExecution": [
      {
        "command": "./approve-network.sh",
        "matcher": "curl|wget|nc "
      }
    ]
  }
}
```

Additional example, verbatim explanation: "beforeShellExecution: The matcher runs against the shell command string. Use it to run hooks only when the command matches a pattern (e.g. network calls, file deletions). The example above runs approve-network.sh only when the command contains curl, wget, or nc."

## Other reference details

- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default". Example shown elsewhere on the page: `{ "command": "./scripts/approve-network.sh", "timeout": 30, "matcher": "curl|wget|nc" }`.
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `beforeShellExecution`.
- No redaction feature is documented for `beforeShellExecution` specifically.
- Prompt-based hook type is also supported for this event per the general "Hook Types" section, e.g.: `{ "hooks": { "beforeShellExecution": [{ "type": "prompt", "prompt": "Does this command look safe to execute? Only allow read-only operations.", "timeout": 10 }] } }`.
- No other known limitations are stated for `beforeShellExecution` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
