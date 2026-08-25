# subagentStop

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called when a subagent completes, errors, or is aborted.
Can trigger follow-up actions."
No skip conditions documented.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: supported.
`subagentStop` is listed "Yes" in the page's cloud agent supported-hooks table under "The following hooks run in cloud agents:".

## Input schema

```json
{
  "subagent_type": "generalPurpose",
  "status": "completed",
  "task": "Explore the authentication flow",
  "description": "Exploring auth flow",
  "summary": "<subagent output summary>",
  "duration_ms": 45000,
  "message_count": 12,
  "tool_call_count": 8,
  "loop_count": 0,
  "modified_files": ["src/auth.ts"],
  "agent_transcript_path": "/path/to/subagent/transcript.txt"
}
```

| Field                    | Type              | Description                                                                    |
| -------------------------- | ----------------- | ----------------------------------------------------------------------------------- |
| `subagent_type`             | string             | Type of subagent: `generalPurpose`, `explore`, `shell`, etc.                        |
| `status`                    | string             | `"completed"`, `"error"`, or `"aborted"`                                             |
| `task`                      | string             | The task description given to the subagent                                          |
| `description`               | string             | Short description of the subagent's purpose                                          |
| `summary`                   | string             | Output summary from the subagent                                                     |
| `duration_ms`               | number             | Execution time in milliseconds                                                       |
| `message_count`             | number             | Number of messages exchanged during the subagent session                            |
| `tool_call_count`           | number             | Number of tool calls the subagent made                                              |
| `loop_count`                | number             | Number of times a `subagentStop` follow-up has already triggered for this subagent (starts at 0) |
| `modified_files`            | string[]           | Files the subagent modified                                                          |
| `agent_transcript_path`     | string \| null     | Path to the subagent's own transcript file (separate from the parent conversation)    |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
  "followup_message": "<auto-continue with this message>"
}
```

| Field                | Type              | Optional | Effect                                                                          |
| --------------------- | ----------------- | -------- | -------------------------------------------------------------------------------------- |
| `followup_message`    | string, optional  | yes      | Auto-continue with this message; only consumed when `status` is `"completed"`. Enables loop-style flows where subagent completion triggers the next iteration |

## Blocking behavior

Does not block the agent loop, fire-and-forget for observational purposes.
Exit code 2 / `continue:false`: not applicable, output has no `continue` or permission fields.
When `followup_message` is provided and `status` is `"completed"`, Cursor automatically submits it as the next user message.
Follow-ups are "subject to the same configurable loop limit as the `stop` hook (default 5, configurable via `loop_limit`)."

## Matcher support

Supported.
The matcher runs against the subagent type (e.g. `explore`, `shell`, `generalPurpose`).

## Other notes

`loop_limit`: defaults to 5 auto follow-ups per script, set `loop_limit` to `null` to remove the cap.
Timeout: no timeout documented specifically for `subagentStop`.
Relationship to `stop`: both hooks support equivalent loop control via `loop_limit`.
