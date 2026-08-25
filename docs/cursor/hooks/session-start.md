# sessionStart

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook (Cmd+K / Agent Chat).
Fires: "Called when a new composer conversation is created."
Skip condition, as stated on the page: "Deferred while cloud agents can still start in a read-only environment.
Hooks don't load there, so a cloud `sessionStart` would fire too late (after the first write) rather than at true session start."

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: not supported.
The page lists `sessionStart` under hooks not available in cloud agents, with reason quoted verbatim above (deferred / would fire too late).

## Input schema

```json
{
  "session_id": "<unique session identifier>",
  "is_background_agent": true | false,
  "composer_mode": "agent" | "ask" | "edit"
}
```

This is the complete input example shown on the page for `sessionStart`; it does not repeat the common-schema base fields inline.

| Field                  | Type            | Description                                                                    |
| ---------------------- | --------------- | -------------------------------------------------------------------------------- |
| `session_id`           | string          | Unique identifier for this session (same as `conversation_id`)                  |
| `is_background_agent`  | boolean         | Whether this is a background agent session vs interactive session                |
| `composer_mode`        | string, optional | The mode the composer is starting in (e.g. "agent", "ask", "edit")              |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present per the page's common schema section.

## Output schema

```json
{
  "env": { "<key>": "<value>" },
  "additional_context": "<context to add to conversation>"
}
```

| Field                | Type   | Optional | Effect                                                                      |
| --------------------- | ------ | -------- | ------------------------------------------------------------------------------ |
| `env`                 | object | yes      | Environment variables to set for this session; available to all subsequent hook executions |
| `additional_context`  | string | yes      | Additional context to add to the conversation's initial system context          |

Note stated on the page: "The schema also accepts `continue` and `user_message` fields, but current callers do not enforce them."

## Blocking behavior

This hook runs as fire-and-forget; the agent loop does not wait for or enforce a blocking response.
Exit code 2: not applicable, blocking is not supported for this hook.
`continue: false`: session creation is not blocked even when `continue` is `false`.

## Matcher support

Not documented.
`sessionStart` is absent from the page's matcher reference table, and its own section has no matcher configuration mentioned.

## Other notes

Timeout: platform default, no override specified in examples.
`loop_limit`: not applicable, this is not a loop-triggering hook.
Stated purpose on the page: "Use it to set up session-specific environment variables or inject additional context."
