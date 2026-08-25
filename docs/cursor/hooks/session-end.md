# sessionEnd

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called when a composer conversation ends.
This is a fire-and-forget hook useful for logging, analytics, or cleanup tasks."
No further skip conditions documented beyond cloud-agent unavailability below.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: not supported.
The page lists `sessionEnd` under hooks not available in cloud agents, with reason: "Cloud agents have no editor-lifetime session boundary.
`sessionEnd` is tied to the IDE session, not a cloud agent chat."

## Input schema

```json
{
  "session_id": "<unique session identifier>",
  "reason": "completed",
  "duration_ms": 45000,
  "is_background_agent": true,
  "final_status": "<status string>",
  "error_message": "<error details if reason is 'error'>"
}
```

| Field                  | Type              | Description                                                                      |
| ---------------------- | ------------------ | ----------------------------------------------------------------------------------- |
| `session_id`           | string             | Unique identifier for the session that is ending                                    |
| `reason`               | string             | How the session ended: "completed", "aborted", "error", "window_close", or "user_close" |
| `duration_ms`          | number             | Total duration of the session in milliseconds                                      |
| `is_background_agent`  | boolean            | Whether this was a background agent session                                        |
| `final_status`         | string             | Final status of the session                                                        |
| `error_message`        | string, optional   | Error message if reason is "error"                                                  |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present per the page's common schema section.

## Output schema

```json
{
}
```

No output fields are documented for `sessionEnd`.
The page states: "The response is logged but not used."

| Field | Type | Optional | Effect |
| ----- | ---- | -------- | ------ |
| (none documented) | -- | -- | -- |

## Blocking behavior

Fire-and-forget.
Quoting the page: "The response is logged but not used."
The agent loop does not wait for or enforce a response.
No blocking occurs regardless of exit codes or response content, since `sessionEnd` has no `continue` or `permission` output field.

## Matcher support

Not documented.
`sessionEnd` is absent from the page's matcher reference table.

## Other notes

No `loop_limit`, timeout override, or `failClosed` configuration is documented for this hook.
Stated purpose on the page: useful for "logging, analytics, or cleanup tasks."
