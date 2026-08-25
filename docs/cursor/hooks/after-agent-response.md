# afterAgentResponse

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called after the agent has completed an assistant message."
No skip conditions documented.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: supported.
`afterAgentResponse` is listed "Yes" in the page's cloud agent supported-hooks table under "The following hooks run in cloud agents:".

## Input schema

```json
{
  "text": "<assistant final text>"
}
```

| Field    | Type    | Description                          |
| -------- | ------- | ---------------------------------------- |
| `text`   | string  | The assistant's final message text        |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
}
```

No output fields are documented for `afterAgentResponse`.

| Field | Type | Optional | Effect |
| ----- | ---- | -------- | ------ |
| (none documented) | -- | -- | -- |

## Blocking behavior

Not documented explicitly as fire-and-forget or blocking.
There is no `continue`/`permission` output field documented for this hook, so exit code 2 has no documented blocking effect here.

## Matcher support

Supported.
Matched against the literal value `"AgentResponse"`.
The page's quickstart example configuration for `afterAgentResponse` omits a `matcher` key, but the matcher reference table confirms the fixed match value above.

## Other notes

No `loop_limit`, timeout default, or other special configuration options are documented for this hook.
