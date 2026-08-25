# afterTabFileEdit

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: tab hook.
Verbatim: "**Tab hooks (inline completions)** fire for autonomous Tab operations." `afterTabFileEdit` is listed under this category as "Post-process Tab edits."

The page also states: "The Tab hooks (`beforeTabFileRead`, `afterTabFileEdit`) apply specifically to inline Tab completions."

Firing condition, verbatim: "Called after Tab (inline completions) edits a file. Useful for formatters or auditing of Tab-written code."

Key differences from `afterFileEdit`, verbatim:
- "Only triggered by Tab, not Agent"
- "Includes detailed edit information: `range`, `old_line`, and `new_line` for precise edit tracking"
- "Useful for fine-grained formatting or analysis of Tab edits"

No further hook-specific skip condition is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook. It is categorized as a Tab hook, applying "specifically to inline Tab completions" (an IDE/desktop-app feature), per the quoted text above.

CLI: not documented.
The page does not mention CLI availability for `afterTabFileEdit` anywhere.

Cloud agents: NOT supported.
`afterTabFileEdit` does not appear in the "Supported hooks" table.
It is listed in the "Hooks not available in cloud agents" table with this reason, verbatim: "beforeTabFileRead / afterTabFileEdit: Tab completions are an IDE feature and don't run in cloud agents."

## Input schema

```json
// Input
{
  "file_path": "<absolute path>",
  "edits": [
    {
      "old_string": "<search>",
      "new_string": "<replace>",
      "range": {
        "start_line_number": 10,
        "start_column": 5,
        "end_line_number": 10,
        "end_column": 20
      },
      "old_line": "<line before edit>",
      "new_line": "<line after edit>"
    }
  ]
}
```

`afterTabFileEdit` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

The page gives no dedicated field table for `afterTabFileEdit`, only the JSON example above plus the "Key differences" bullets.

| Field              | Type   | Description                                                                                                                  |
|--------------------|--------|-----------------------------------------------------------------------------------------------------------------------------------|
| file_path          | string | Not documented (JSON example shows the absolute path to the edited file)                                                          |
| edits              | array  | Not documented as a whole; each entry has old_string, new_string, range, old_line, and new_line (see field breakdown below)       |
| edits[].old_string | string | Not documented (JSON example shows the search text)                                                                                |
| edits[].new_string | string | Not documented (JSON example shows the replacement text)                                                                           |
| edits[].range      | object | Not documented; JSON example shows start_line_number, start_column, end_line_number, end_column                                   |
| edits[].old_line   | string | Not documented (JSON example: "<line before edit>")                                                                                |
| edits[].new_line   | string | Not documented (JSON example: "<line after edit>")                                                                                 |

## Output schema

```json
// Output
{
  // No output fields currently supported
}
```

The JSON example on the page explicitly comments "No output fields currently supported" for this hook's output. There is no output field table.

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

Since the Tab edit has already been applied by the time this hook fires and it has no output fields, the page gives no indication that exit code `2` has any effect for `afterTabFileEdit`; this is not documented for this hook specifically.

`failClosed` (general per-script option): "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`. No `afterTabFileEdit`-specific note is given.

## Matcher support

Not documented. The "Available matchers by hook" list on the page covers `preToolUse`/`postToolUse`/`postToolUseFailure`, `subagentStart`/`subagentStop`, `beforeShellExecution`/`afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `stop`, `afterAgentResponse`, and `afterAgentThought`, but does not include an entry for `afterTabFileEdit`.

## Other reference details

- Cloud agents: this hook is explicitly excluded from cloud execution (see Surface availability above) because Tab completions don't run in cloud agents at all.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `afterTabFileEdit`.
- The page's own example filename for this hook implies a formatting use case: `{ "hooks": { "afterTabFileEdit": [{ "command": "./format-tab.sh" }] } }`.
- No other known limitations are stated for `afterTabFileEdit` beyond its cloud-agent exclusion.
