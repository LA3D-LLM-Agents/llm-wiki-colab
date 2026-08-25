# Cursor Hooks Common Schema

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Input (all hooks)

All hooks receive a base set of fields in addition to their hook-specific fields:

```json
{
  "conversation_id": "string",
  "generation_id": "string",
  "model": "string",
  "model_id": "string",
  "model_params": [{ "id": "string", "value": "string" }],
  "hook_event_name": "string",
  "cursor_version": "string",
  "workspace_roots": ["<path>"],
  "user_email": "string | null",
  "transcript_path": "string | null"
}
```

| Field              | Type                     | Description                                                                                  |
|----------------------|----------------------------|--------------------------------------------------------------------------------------------------|
| `conversation_id`      | string                       | Stable ID of the conversation across many turns.                                                  |
| `generation_id`        | string                       | The current generation that changes with every user message.                                       |
| `model`                | string                       | Legacy model slug configured for the composer that triggered the hook.                             |
| `model_id`              | string (optional)            | Structured ID for the selected model, when available.                                               |
| `model_params`          | array (optional)             | Selected model parameters, such as thinking, context, or effort.  Each item has an `id` and `value`. |
| `hook_event_name`       | string                       | Which hook is being run.                                                                             |
| `cursor_version`        | string                       | Cursor application version (e.g. `"1.7.2"`).                                                         |
| `workspace_roots`       | string[]                     | The list of root folders in the workspace (normally just one, but multiroot workspaces can have multiple). |
| `user_email`            | string \| null               | Email address of the authenticated user, if available.                                              |
| `transcript_path`       | string \| null               | Path to the main conversation transcript file (null if transcripts disabled).                        |

## App lifecycle omissions

The page notes that app lifecycle hooks omit some of the above fields:

"App lifecycle hooks (`workspaceOpen`) fire outside any agent session, so the request omits `conversation_id`, `generation_id`, `model`, `session_id`, and `transcript_path`."

This sentence names a `session_id` field as one of the omitted fields, but no field literally named `session_id` appears in the common schema table or its example JSON on the page.
This is an inconsistency in the source page itself, reproduced here verbatim rather than corrected; not documented as an actual schema field.
