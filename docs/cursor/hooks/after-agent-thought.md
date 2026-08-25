# afterAgentThought

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook.
Fires: "Called after the agent completes a thinking block.
Useful for observing the agent's reasoning process."
No skip conditions documented.

## Surface availability

Desktop app: not documented.
CLI: not documented.
Cloud agents: supported.
`afterAgentThought` is listed "Yes" in the page's cloud agent supported-hooks table under "The following hooks run in cloud agents:".

## Input schema

```json
{
  "text": "<fully aggregated thinking text>",
  "duration_ms": 5000
}
```

| Field            | Type               | Description                                                |
| ----------------- | ------------------ | ---------------------------------------------------------------- |
| `text`             | string              | Fully aggregated thinking text for the completed block             |
| `duration_ms`      | number, optional    | Duration in milliseconds for the thinking block                    |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
}
```

No output fields are documented for `afterAgentThought`.
This is an observational hook only.

| Field | Type | Optional | Effect |
| ----- | ---- | -------- | ------ |
| (none documented) | -- | -- | -- |

## Blocking behavior

Not documented explicitly as fire-and-forget or blocking; the page only says the hook is "Called after the agent completes a thinking block."
No exit code 2 blocking or `continue: false` mechanism applies, there is no `continue`/`permission` output field.

## Matcher support

Supported.
Matched against the literal value `"AgentThought"`.
The page's quickstart example configuration for `afterAgentThought` omits a `matcher` key, but the matcher reference table confirms the fixed match value above.

## Other notes

Timeout: platform default, no hook-specific override documented.
`loop_limit`: not applicable, this is an observational, fire-and-forget hook.
