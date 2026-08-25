# Cursor Hooks Configuration

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Configuration file shape

Hooks are configured in a `hooks.json` file.
The full JSON shape, as shown on the page:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [{ "command": "./session-init.sh" }],
    "sessionEnd": [{ "command": "./audit.sh" }],
    "preToolUse": [
      {
        "command": "./hooks/validate-tool.sh",
        "matcher": "Shell|Read|Write"
      }
    ],
    "postToolUse": [{ "command": "./hooks/audit-tool.sh" }],
    "subagentStart": [{ "command": "./hooks/validate-subagent.sh" }],
    "subagentStop": [{ "command": "./hooks/audit-subagent.sh" }],
    "beforeShellExecution": [{ "command": "./script.sh" }],
    "afterShellExecution": [{ "command": "./script.sh" }],
    "afterMCPExecution": [{ "command": "./script.sh" }],
    "afterFileEdit": [{ "command": "./format.sh" }],
    "preCompact": [{ "command": "./audit.sh" }],
    "stop": [{ "command": "./audit.sh", "loop_limit": 10 }],
    "beforeTabFileRead": [{ "command": "./redact-secrets-tab.sh" }],
    "afterTabFileEdit": [{ "command": "./format-tab.sh" }],
    "workspaceOpen": [{ "command": "./register-workspace-plugins.sh" }]
  }
}
```

The page states: "The `hooks` object maps hook names to arrays of hook definitions.
Each definition currently supports a `command` property that can be a shell string, an absolute path, or a relative path."

## Global configuration options

| Option    | Type   | Default | Description         |
|-----------|--------|---------|-----------------------|
| `version`  | number  | `1`      | Config schema version. |

## Per-script configuration options

| Option        | Type                                | Default            | Description                                                                                     |
|-----------------|--------------------------------------|-----------------------|----------------------------------------------------------------------------------------------------|
| `command`        | string                                | required               | Script path or command.                                                                            |
| `type`           | `"command"` \| `"prompt"`              | `"command"`             | Hook execution type.                                                                                |
| `timeout`        | number                                | platform default       | Execution timeout in seconds.                                                                       |
| `loop_limit`     | number \| null                        | `5`                     | Per-script loop limit for `stop`/`subagentStop` hooks. `null` means no limit. Default is `5` for Cursor hooks, `null` for Claude Code hooks. |
| `failClosed`     | boolean                               | `false`                 | When `true`, hook failures (crash, timeout, invalid JSON) block the action instead of allowing it through. Useful for security-critical hooks. |
| `matcher`        | object                                | not documented (shown as a plain dash on the page) | Filter criteria for when hook runs.                                |

## Matcher configuration

Matchers let you filter when a hook runs.
Which field the matcher applies to depends on the hook.

Available matchers by hook, as stated on the page:

- **preToolUse / postToolUse / postToolUseFailure**: Filter by tool type. Values include `Shell`, `Read`, `Write`, `Grep`, `Delete`, `Task`, and MCP tools using the `MCP:<tool_name>` format.
- **subagentStart / subagentStop**: Filter by subagent type (`generalPurpose`, `explore`, `shell`, etc.).
- **beforeShellExecution / afterShellExecution**: Filter by the shell command text; the matcher is matched against the full command string.
- **beforeReadFile**: Filter by tool type (`TabRead`, `Read`, etc.).
- **afterFileEdit**: Filter by tool type (`TabWrite`, `Write`, etc.).
- **beforeSubmitPrompt**: Matched against the value `UserPromptSubmit`.
- **stop**: Matched against the value `Stop`.
- **afterAgentResponse**: Matched against the value `AgentResponse`.
- **afterAgentThought**: Matched against the value `AgentThought`.

Example: `"matcher": "curl|wget|nc"` runs the hook only when the shell command contains those patterns.

## Definition locations and priority order

Hooks can be defined at multiple levels, distributed via version control, MDM, or a cloud dashboard.

### Project hooks (version control)

Place a `hooks.json` file at `<project-root>/.cursor/hooks.json` and commit it to your repository.

### User hooks

User-level hooks live at `~/.cursor/hooks.json`, with scripts under `~/.cursor/hooks/`.

### MDM distribution (enterprise, system-wide)

System-wide hook configuration locations, by platform:

- macOS: `/Library/Application Support/Cursor/hooks.json`
- Linux/WSL: `/etc/cursor/hooks.json`
- Windows: `C:\ProgramData\Cursor\hooks.json`

### Cloud distribution (enterprise only)

Configured in the web dashboard and synced to all team members automatically.

### Priority order

The page states the priority order as: "Priority order (highest to lowest): Enterprise → Team → Project → User".

## Working directory semantics

- Project hooks run from the project root.
  The docs give explicit path guidance: "For project hooks, use paths like `.cursor/hooks/script.sh` (relative to project root), not `./hooks/script.sh` (which would look for `<project>/hooks/script.sh`)."
- User hooks run from `~/.cursor/`.
- Enterprise hooks run from the enterprise config directory.
- Team hooks run from the managed hooks directory.

## Reload behavior

Cursor watches `hooks.json` files and reloads them on save.
If hooks still do not load, restart Cursor.
