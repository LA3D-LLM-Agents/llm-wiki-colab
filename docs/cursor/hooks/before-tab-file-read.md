# beforeTabFileRead

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Category and timing

Category: tab hook.
Verbatim: "**Tab hooks (inline completions)** fire for autonomous Tab operations." `beforeTabFileRead` is listed under this category as "Control file access for Tab completions."

The page also states: "The Tab hooks (`beforeTabFileRead`, `afterTabFileEdit`) apply specifically to inline Tab completions."

Firing condition, verbatim: "Called before Tab (inline completions) reads a file. Enable redaction or access control before Tab accesses file contents."

Key differences from `beforeReadFile`, verbatim:
- "Only triggered by Tab, not Agent"
- "Does not include `attachments` field (Tab doesn't use prompt attachments)"
- "Useful for applying different policies to autonomous Tab operations"

No further hook-specific skip condition is documented.

## Surface availability

Desktop app: not stated in an explicit "desktop app" line for this hook. It is categorized as a Tab hook, applying "specifically to inline Tab completions" (an IDE/desktop-app feature), per the quoted text above.

CLI: not documented.
The page does not mention CLI availability for `beforeTabFileRead` anywhere.

Cloud agents: NOT supported.
`beforeTabFileRead` does not appear in the "Supported hooks" table.
It is listed in the "Hooks not available in cloud agents" table with this reason, verbatim: "beforeTabFileRead / afterTabFileEdit: Tab completions are an IDE feature and don't run in cloud agents."

## Input schema

```json
// Input
{
  "file_path": "<absolute path>",
  "content": "<file contents>"
}
```

`beforeTabFileRead` also receives the common base fields documented under "Input (all hooks)" (`conversation_id`, `generation_id`, `model`, `model_id`, `model_params`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`).

The page gives no dedicated field table for `beforeTabFileRead`, only the JSON example above plus the "Key differences" bullets.

| Field     | Type   | Description                                                                                                                                                            |
|-----------|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| file_path | string | Not documented (JSON example shows the absolute path to the file); same field name as beforeReadFile, which documents it as "Absolute path to the file being read"      |
| content   | string | Not documented (JSON example shows the full file contents); same field name as beforeReadFile, which documents it as "Full contents of the file"                        |

Note: unlike `beforeReadFile`, this input has no `attachments` field, per the "Key differences" bullet above.

## Output schema

```json
// Output
{
  "permission": "allow" | "deny"
}
```

| Output Field | Type   | Description                                                                                                                            |
|--------------|--------|----------------------------------------------------------------------------------------------------------------------------------------|
| permission   | string | Not documented for beforeTabFileRead specifically; beforeReadFile documents the same field as "'allow' to proceed, 'deny' to block"    |

Note: unlike `beforeReadFile`'s output, this schema has no `user_message` field.

## Blocking behavior

The generic exit code semantics documented for command hooks are:

- Exit code `0` - Hook succeeded, use the JSON output.
- Exit code `2` - Block the action (equivalent to returning `permission: "deny"`).
- Other exit codes - Hook failed, action proceeds (fail-open by default).

No `beforeTabFileRead`-specific fail-open/fail-closed note is given (contrast with `beforeReadFile`, which has one). The general `failClosed` per-script option applies: "When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks." Default is `false`.

The agent loop (Tab's autonomous operation loop) waits on this hook for a permission decision before Tab reads the file (implied by the access-control/redaction firing description and the permission output; the page does not use the word "waits" or "synchronous" explicitly).

## Matcher support

Not documented. The "Available matchers by hook" list on the page covers `preToolUse`/`postToolUse`/`postToolUseFailure`, `subagentStart`/`subagentStop`, `beforeShellExecution`/`afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `stop`, `afterAgentResponse`, and `afterAgentThought`, but does not include an entry for `beforeTabFileRead`.

## Other reference details

- Cloud agents: this hook is explicitly excluded from cloud execution (see Surface availability above) because Tab completions don't run in cloud agents at all.
- `timeout`: general per-script option, "Execution timeout in seconds", default is "platform default".
- `loop_limit`: general per-script option, applies only to `stop`/`subagentStop` hooks, not to `beforeTabFileRead`.
- The page's own example filename for this hook implies a redaction use case: `{ "hooks": { "beforeTabFileRead": [{ "command": "./redact-secrets-tab.sh" }] } }`. This is an example script name in a sample config, not a description of a built-in redaction feature.
- No other known limitations are stated for `beforeTabFileRead` beyond its cloud-agent exclusion.
