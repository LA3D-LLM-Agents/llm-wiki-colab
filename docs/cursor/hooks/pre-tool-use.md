# preToolUse

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`preToolUse` is listed under the category as one of the "Generic tool use hooks (fires for all tools)", grouped with `postToolUse` and `postToolUseFailure`.

Firing condition, verbatim: "Called before any tool execution. This is a generic hook that fires for all tool types (Shell, Read, Write, MCP, Task, etc.). Use matchers to filter by specific tools."

No hook-specific skip condition is documented for `preToolUse` beyond the general cloud-agent caveat below.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `preToolUse` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `preToolUse` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `preToolUse` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// Input
{
  "tool_name": "Shell",
  "tool_input": { "command": "npm install", "working_directory": "/project" },
  "tool_use_id": "abc123",
  "cwd": "/project",
  "model": "claude-opus-4-7-thinking-max",
  "model_id": "claude-opus-4-7",
  "model_params": [
    { "id": "thinking", "value": "true" },
    { "id": "context", "value": "1m" },
    { "id": "effort", "value": "max" }
  ],
  "agent_message": "Installing dependencies..."
}
```

`preToolUse` also receives the common base fields documented under "Input (all hooks)":

```json
{
  "conversation_id": "string",
  "generation_id": "string",
  "model": "string",
  "model_id": "string",
  "model_params": [{ "id": "string", "value": "string" }],
  "hook_event_name": "string",
  "cursor_version": "string",
  "workspace_roots": ["<path>"],
  "user_email": "string | null",
  "transcript_path": "string | null"
}
```

The page does not give a dedicated "Input Field" table for `preToolUse` beyond the JSON example, so the hook-specific field descriptions below are marked "not documented" where the page gives no prose description.

| Field         | Type   | Description                                                                                        |
|---------------|--------|-----------------------------------------------------------------------------------------------------|
| tool_name     | string | Not documented (JSON example shows the tool type, e.g. "Shell")                                     |
| tool_input    | object | Not documented (JSON example shows tool-specific parameters, e.g. { command, working_directory })   |
| tool_use_id   | string | Not documented (JSON example shows a unique identifier, e.g. "abc123")                              |
| cwd           | string | Not documented (JSON example shows the working directory, e.g. "/project")                          |
| agent_message | string | Not documented (JSON example shows agent-provided context, e.g. "Installing dependencies...")       |

Common base fields (from "Input (all hooks)"):

| Field           | Type              | Description                                                                                                |
|-----------------|-------------------|--------------------------------------------------------------------------------------------------------------|
| conversation_id | string            | Stable ID of the conversation across many turns                                                             |
| generation_id   | string            | The current generation that changes with every user message                                                 |
| model           | string            | Legacy model slug configured for the composer that triggered the hook                                       |
| model_id        | string (optional) | Structured ID for the selected model, when available                                                        |
| model_params    | array (optional)  | Selected model parameters, such as thinking, context, or effort. Each item has an id and value.              |
| hook_event_name | string            | Which hook is being run                                                                                      |
| cursor_version  | string            | Cursor application version (e.g. "1.7.2")                                                                    |
| workspace_roots | string[]          | The list of root folders in the workspace (normally just one, but multiroot workspaces can have multiple)    |
| user_email      | string \| null    | Email address of the authenticated user, if available                                                       |
| transcript_path | string \| null    | Path to the main conversation transcript file (null if transcripts disabled)                                |

## Output schema

```json
// Output
{
  "permission": "allow" | "deny",
  "user_message": "<message shown in client when denied>",
  "agent_message": "<message sent to agent when denied>",
  "updated_input": { "command": "npm ci" }
}
```

| Output Field  | Type              | Description                                                                                                   |
|---------------|-------------------|------------------------------------------------------------------------------------------------------------------|
| permission    | string            | "allow" to proceed, "deny" to block. "ask" is accepted by the schema but not enforced for preToolUse today.     |
| user_message  | string (optional) | Message shown to the user when the action is denied                                                             |
| agent_message | string (optional) | Message fed back to the agent when the action is denied                                                          |
| updated_input | object (optional) | Modified tool input to use instead                                                                               |

## Blocking behavior

The generic exit code semantics documented for command hooks apply:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

The Troubleshooting section states, verbatim: "Exit code `2` from command hooks blocks the action (equivalent to returning `permission: "deny"`). This matches Claude Code behavior for compatibility."

`failClosed` (per-script configuration option, general to all hooks): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`.
No `preToolUse`-specific fail-open/fail-closed note is given beyond this general option description.

## Matcher support

Verbatim: "preToolUse / postToolUse / postToolUseFailure: Filter by tool type. Values include `Shell`, `Read`, `Write`, `Grep`, `Delete`, `Task`, and MCP tools using the `MCP:<tool_name>` format."

Example configuration shown on the page:

```json
{
  "hooks": {
    "preToolUse": [
      {
        "command": "./validate-shell.sh",
        "matcher": "Shell"
      }
    ]
  }
}
```

## Other reference details

- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `preToolUse`. Default is `5` for Cursor hooks, `null` (no limit) for Claude Code hooks; `null` means no limit.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- No redaction feature is documented for `preToolUse` specifically.
- No known limitations are stated for `preToolUse` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
