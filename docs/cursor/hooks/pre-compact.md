# preCompact

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called before context window compaction/summarization occurs.
This is an observational hook that cannot block or modify the compaction behavior."
No further skip conditions documented.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: supported.
`preCompact` is listed "Yes" in the page's cloud agent supported-hooks table under "The following hooks run in cloud agents:".

## Input schema

```json
{
  "trigger": "auto",
  "context_usage_percent": 85,
  "context_tokens": 120000,
  "context_window_size": 128000,
  "message_count": 45,
  "messages_to_compact": 30,
  "is_first_compaction": true
}
```

| Field                     | Type      | Description                                                    |
| -------------------------- | --------- | -------------------------------------------------------------------- |
| `trigger`                  | string    | What triggered the compaction: "auto" or "manual"                    |
| `context_usage_percent`    | number    | Current context window usage as a percentage (0-100)                 |
| `context_tokens`           | number    | Current context window token count                                   |
| `context_window_size`      | number    | Maximum context window size in tokens                                |
| `message_count`            | number    | Number of messages in the conversation                               |
| `messages_to_compact`      | number    | Number of messages that will be summarized                           |
| `is_first_compaction`      | boolean   | Whether this is the first compaction for this conversation            |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
  "user_message": "<message to show when compaction occurs>"
}
```

| Field            | Type              | Optional | Effect                                                  |
| ----------------- | ----------------- | -------- | -------------------------------------------------------------- |
| `user_message`    | string, optional  | yes      | Message to show to the user when compaction occurs              |

No `additional_context`, `env`, `continue`, or `pluginPaths` fields are supported for `preCompact`.

## Blocking behavior

Fire-and-forget / observational.
Quoting the page: "This is an observational hook that cannot block or modify the compaction behavior."
Exit codes and any `continue` field have no effect, compaction proceeds regardless.

## Matcher support

Not documented.
`preCompact` is absent from the page's matcher reference table.

## Other notes

Timeout: platform default, no custom override mentioned.
`loop_limit`: not applicable, this is an observational hook and cannot trigger follow-ups.
Stated purpose on the page: "Useful for logging when compaction happens or notifying users."
