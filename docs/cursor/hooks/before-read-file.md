# beforeReadFile

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: agent hook.
Agent hooks fire during an agent session ("Agent hooks (Cmd+K/Agent Chat) fire during an agent session").
`beforeReadFile` is listed under "Control file access and edits", paired with `afterFileEdit`.

Firing condition, verbatim: "Called before Agent reads a file. Use for access control to block sensitive files from being sent to the model."

No hook-specific skip condition beyond the general cloud-agent caveat below is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook.
The page groups `beforeReadFile` under "Agent hooks (Cmd+K/Agent Chat)" and separately states: "The Agent hooks (`sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`) apply to Cmd+K and Agent Chat operations."

CLI: not documented.
The page does not mention CLI availability for `beforeReadFile` anywhere.

Cloud agents: supported.
The "Supported hooks" table lists `beforeReadFile` as "Yes".
General cloud-agent context that applies to this hook: "Cloud agents run command-based hooks from your repository. If you have hooks defined in `.cursor/hooks.json` at the root of your project, cloud agents pick them up and run them during their work."
Caveat: "Cloud agents sometimes begin in a read-only environment for early exploratory turns. Hooks do not run during those turns. They start once the agent has a writable environment."
Also: "Cloud agents run command-based hooks only. Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

## Input schema

```json
// Input
{
  "file_path": "<absolute path>",
  "content": "<file contents>",
  "attachments": [
    {
      "type": "file" | "rule",
      "file_path": "<absolute path>"
    }
  ]
}
```

`beforeReadFile` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

| Field       | Type   | Description                                                                                                 |
|-------------|--------|-----------------------------------------------------------------------------------------------------------------|
| file_path   | string | Absolute path to the file being read                                                                            |
| content     | string | Full contents of the file                                                                                       |
| attachments | array  | Context attachments associated with the prompt. Each entry has a type ("file" or "rule") and a file_path.       |

## Output schema

```json
// Output
{
  "permission": "allow" | "deny",
  "user_message": "<message shown when denied>"
}
```

| Output Field | Type              | Description                            |
|--------------|-------------------|--------------------------------------------|
| permission   | string            | "allow" to proceed, "deny" to block          |
| user_message | string (optional) | Message shown to user when denied            |

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

Hook-specific failure note, verbatim: "By default, `beforeReadFile` hook failures (crash, timeout, invalid JSON) are logged and the read is allowed through. Set `failClosed: true` on the hook definition to block the read on failure instead."

The agent loop waits on this hook for a permission decision before the file read completes (implied by the access-control firing description and the exit-code/permission blocking semantics; the page does not use the word "waits" or "synchronous" explicitly).

## Matcher support

Verbatim: "beforeReadFile: Filter by tool type (`TabRead`, `Read`, etc.)."

## Other reference details

- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `beforeReadFile`.
- No built-in redaction feature is documented; access control is achieved by returning `permission: "deny"`.
- No other known limitations are stated for `beforeReadFile` beyond the general cloud read-only-early-turns caveat and the command-hooks-only limitation in cloud agents.
- Compare with `beforeTabFileRead`: the page states the "Key differences" are that `beforeTabFileRead` "Only triggered by Tab, not Agent" and "Does not include `attachments` field (Tab doesn't use prompt attachments)".
