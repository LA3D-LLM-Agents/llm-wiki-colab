# stop

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called when the agent loop ends.
Can optionally auto-submit a follow-up user message to keep iterating."
No skip conditions documented.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: supported.
`stop` is listed "Yes" in the page's cloud agent supported-hooks table ("The following hooks run in cloud agents:").

## Input schema

```json
{
  "status": "completed",
  "loop_count": 0
}
```

| Field         | Type    | Description                                                                              |
| ------------- | ------- | -------------------------------------------------------------------------------------------- |
| `status`      | string  | Agent completion state: "completed", "aborted", or "error"                                   |
| `loop_count`  | number  | How many times the stop hook has already triggered an automatic follow-up for this conversation (starts at 0) |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
  "followup_message": "<message text>"
}
```

| Field                | Type              | Optional | Effect                                                                                          |
| --------------------- | ----------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `followup_message`    | string, optional  | yes      | "When provided and non-empty, Cursor will automatically submit it as the next user message.
This enables loop-style flows" |

## Blocking behavior

Not documented explicitly as fire-and-forget or blocking; the page only says the hook is "Called when the agent loop ends" with an optional `followup_message` output.
No exit code 2 / `continue:false` blocking mechanism applies (this is an output-only hook, no `continue` or `permission` field).
Auto follow-ups triggered via `followup_message` are "subject to the same configurable loop limit as the `stop` hook (default 5, configurable via `loop_limit`)."

## Matcher support

Supported.
Matched against the literal value `"Stop"`.
The page's quickstart example configuration for `stop` omits a `matcher` key, but the matcher reference table confirms the fixed match value above.

## Other notes

`loop_limit`: configurable per script, default 5 for Cursor, `null` for Claude Code (per the page's general loop-limiting note); set to `null` to remove the cap.
No timeout override documented specifically for `stop`; platform default applies.
