# Cursor Hook Types

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

There are two hook execution types: command-based and prompt-based, selected via the per-script `type` field (`"command"` or `"prompt"`, default `"command"`).

## Command-based hooks

Command hooks execute shell scripts that receive JSON input via stdin and return JSON output via stdout.

### Invocation protocol

- Input: the hook script receives JSON on standard input.
- Output: the hook script must output JSON to standard output.

### Exit codes

| Exit code       | Meaning                                                              |
|-------------------|-------------------------------------------------------------------------|
| `0`                | Hook succeeded, use the JSON output.                                     |
| `2`                 | Block the action (equivalent to returning `permission: "deny"`).          |
| other              | Hook failed, action proceeds (fail-open by default).                      |

The Troubleshooting section restates the exit-code-2 behavior: "Exit code `2` from command hooks blocks the action (equivalent to returning `permission: "deny"`)."

Example configuration:

```json
{
  "hooks": {
    "beforeShellExecution": [
      {
        "command": "./scripts/approve-network.sh",
        "timeout": 30,
        "matcher": "curl|wget|nc"
      }
    ]
  }
}
```

## Prompt-based hooks

Prompt hooks use an LLM to evaluate conditions via natural language.

### JSON shape

```json
{
  "hooks": {
    "beforeShellExecution": [
      {
        "type": "prompt",
        "prompt": "Does this command look safe to execute? Only allow read-only operations.",
        "timeout": 10
      }
    ]
  }
}
```

### Fields and behavior

- `type`: `"prompt"`.
- `prompt`: the natural-language condition text.
- Returns a structured `{ ok: boolean, reason?: string }` response.
- Uses a fast model for quick evaluation.
- `$$ARGUMENTS` placeholder is auto-replaced with hook input JSON.
- If `$$ARGUMENTS` is absent, hook input is auto-appended.
- Optional `model` field to override the default LLM model.

## Documented execution-type limits

The page states, in the Cloud agent support section: "Cloud agents run **command-based hooks** only.
Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment."

Beyond this cloud-agent restriction, the page does not document any other limits on which hook events may use `type: "prompt"` versus `type: "command"`; not documented.
