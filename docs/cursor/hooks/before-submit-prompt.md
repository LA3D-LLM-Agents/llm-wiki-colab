# beforeSubmitPrompt

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

Agent hook (Cmd+K / Agent Chat).
Fires: "Called right after user hits send but before backend request.
Can prevent submission."
No skip conditions documented.

## Surface availability

Desktop app: not documented (the hook is grouped under agent hooks, which apply to "Cmd+K and Agent Chat operations", but the page gives no desktop-specific wording).
CLI: not documented.
Cloud agents: supported.
`beforeSubmitPrompt` is listed "Yes" in the page's cloud agent supported-hooks table under "The following hooks run in cloud agents:".

## Input schema

```json
{
  "prompt": "<user prompt text>",
  "attachments": [
    {
      "type": "file",
      "file_path": "<absolute path>"
    }
  ]
}
```

| Field                      | Type    | Description                                                       |
| --------------------------- | ------- | ----------------------------------------------------------------------- |
| `prompt`                    | string  | User prompt text                                                        |
| `attachments`               | array   | Context attachments associated with the prompt                          |
| `attachments[].type`        | string  | Either "file" or "rule"                                                 |
| `attachments[].file_path`   | string  | Absolute path of the attached file                                      |

Base fields common to all hooks (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`) are also present.

## Output schema

```json
{
  "continue": true,
  "user_message": "<message shown to user when blocked>"
}
```

| Field            | Type              | Optional | Effect                                                     |
| ----------------- | ----------------- | -------- | ---------------------------------------------------------------- |
| `continue`        | boolean           | no       | Whether to allow the prompt submission to proceed                |
| `user_message`    | string, optional  | yes      | Message shown to the user when the prompt is blocked              |

## Blocking behavior

Blocking: the agent loop waits for and enforces the response.
When `continue` is `false`, the submission is prevented and the user sees the optional `user_message`.
Per the page's general exit-code semantics for command hooks, exit code 2 blocks the action (equivalent to returning a deny/`continue:false` result), although `beforeSubmitPrompt` specifically uses the `continue` field rather than a `permission` field.
This is not a fire-and-forget hook.

## Matcher support

Supported.
Matched against the literal value `"UserPromptSubmit"`.
The page's quickstart example configuration for `beforeSubmitPrompt` omits a `matcher` key, but the matcher reference table confirms the fixed match value above.

## Other notes

No timeout default specified for this hook; platform default applies, configurable per-script.
`loop_limit`: not applicable to `beforeSubmitPrompt`.
`failClosed`: not mentioned for this hook specifically.
