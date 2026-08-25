# workspaceOpen

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and firing conditions

App lifecycle hook.
Fires: "Fires once when Cursor opens a workspace and again on every workspace folder change."
Skip condition, quoted from the page: "Skipped when the window has zero workspace folders."

## Surface availability

Desktop app: supported.
The page states: "Runs in the Cursor desktop app and CLI."
CLI: supported, per the same quote above.
Cloud agents: not supported.
The page lists `workspaceOpen` under hooks not available in cloud agents, with reason: "This is an IDE lifecycle hook and doesn't apply to cloud agents."

## Input schema

```json
{
  "hook_event_name": "workspaceOpen",
  "cursor_version": "string",
  "workspace_roots": ["<absolute path>"],
  "user_email": "string | null"
}
```

| Field               | Type            | Description                                    |
| -------------------- | --------------- | --------------------------------------------------- |
| `hook_event_name`    | string          | Identifies the hook being run                       |
| `cursor_version`     | string          | Cursor application version                          |
| `workspace_roots`    | string[]        | Absolute paths to workspace folders                 |
| `user_email`         | string \| null  | Authenticated user email if available               |

## Output schema

```json
{
  "pluginPaths": ["<absolute path>", "..."]
}
```

| Field          | Type      | Optional | Effect                                                             |
| -------------- | --------- | -------- | ------------------------------------------------------------------------ |
| `pluginPaths`  | string[]  | yes      | "Absolute paths to plugin directories to load for the current workspace" |

## Blocking behavior

Fire-and-forget.
The workspace does not wait for hook completion before proceeding.
No exit code 2 or `continue` field blocking semantics apply, `workspaceOpen` has no `continue`/`permission` output field.

## Matcher support

Not documented.
`workspaceOpen` is absent from the page's matcher reference table.

## Other notes

Does not fire when the window has zero workspace folders (see skip condition above).
No timeout default specified in the documentation for this hook.
No `loop_limit` applicable, this is not an iterative/loop-triggering hook.
Runs outside any agent conversation/session context.
