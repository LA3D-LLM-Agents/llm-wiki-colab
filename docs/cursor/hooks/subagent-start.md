# subagentStart

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called before spawning a subagent (Task tool).
Can allow or deny subagent creation."
No skip conditions documented.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: supported.
`subagentStart` is listed "Yes" in the page's cloud agent supported-hooks table under "The following hooks run in cloud agents:".

## Input schema

```json
{
  "subagent_id": "abc-123",
  "subagent_type": "generalPurpose",
  "task": "Explore the authentication flow",
  "parent_conversation_id": "conv-456",
  "tool_call_id": "tc-789",
  "subagent_model": "claude-sonnet-4-20250514",
  "is_parallel_worker": false,
  "git_branch": "feature/auth"
}
```

| Field                       | Type              | Description                                                     |
| ----------------------------- | ----------------- | ----------------------------------------------------------------- |
| `subagent_id`                 | string             | Unique identifier for this subagent instance                       |
| `subagent_type`               | string             | Type of subagent: `generalPurpose`, `explore`, `shell`, etc.       |
| `task`                        | string             | The task description given to the subagent                         |
| `parent_conversation_id`      | string             | Conversation ID of the parent agent session                        |
| `tool_call_id`                | string             | ID of the tool call that triggered the subagent                    |
| `subagent_model`              | string             | Model the subagent will use                                        |
| `is_parallel_worker`          | boolean            | Whether this subagent is running as a parallel worker               |
| `git_branch`                  | string, optional   | Git branch the subagent will operate on, if applicable              |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
  "permission": "allow",
  "user_message": "<message shown to the user when the subagent is denied>"
}
```

| Field            | Type              | Optional | Effect                                                                                          |
| ----------------- | ----------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `permission`       | string             | no       | `"allow"` to proceed, `"deny"` to block; `"ask"` is not supported for `subagentStart` and is treated as `"deny"` |
| `user_message`     | string, optional   | yes      | Message shown to the user when the subagent is denied                                                 |

No `additional_context`, `env`, `continue`, or `pluginPaths` fields are supported.

## Blocking behavior

The agent loop waits for a response before proceeding.
Exit code 2: equivalent to `permission: "deny"`, blocks subagent creation.
Not fire-and-forget, this is a blocking hook that enforces the permission decision.

## Matcher support

Supported.
Stated purpose: "Use it to run hooks only when a specific kind of subagent is started."
The matcher runs against the subagent type, values include `explore`, `shell`, `generalPurpose`, etc.
Example: `"matcher": "explore|shell"` runs the hook only for explore or shell subagents.

## Other notes

`loop_limit`: not applicable to `subagentStart`, this applies only to `stop` and `subagentStop`.
Timeout: not explicitly documented for this hook, platform default applies.
`failClosed`: not mentioned for `subagentStart`.
