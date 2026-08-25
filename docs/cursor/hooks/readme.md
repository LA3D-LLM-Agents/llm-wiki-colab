# Cursor Hooks Reference

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

This is an extracted reference for Cursor's hooks system, covering the agent hooks, tab hooks, and app lifecycle hooks that let scripts observe, control, and extend the agent loop.
Hooks are spawned processes that communicate over stdio using JSON in both directions.
They run before or after defined stages of the agent loop and can observe, block, or modify behavior.
Hooks are defined in `hooks.json` files at the project or user level, or installed through plugins from Customize.

## Collection files

| File                          | Content                                                                       |
|--------------------------------|--------------------------------------------------------------------------------|
| `readme.md`                    | This index.                                                                    |
| `configuration.md`             | The `hooks.json` format, configuration options, matcher rules, definition locations and priority. |
| `hook-types.md`                | Command-based vs prompt-based hooks, invocation protocol, exit codes.          |
| `common-schema.md`             | Fields every hook receives on stdin.                                           |
| `environment-variables.md`     | Environment variables available to hook scripts.                               |
| `cloud-agents.md`              | Cloud agent support: which hooks run, configuration sources, execution limits. |
| per-event files (see table below) | One file per hook event, written by other agents.                          |

## Hook categories

### Agent hooks (Cmd+K/Agent Chat)

These fire during an agent session:

- `sessionStart` / `sessionEnd` — session lifecycle management.
- `preToolUse` / `postToolUse` / `postToolUseFailure` — generic tool use hooks (fires for all tools).
- `subagentStart` / `subagentStop` — subagent (Task tool) lifecycle.
- `beforeShellExecution` / `afterShellExecution` — control shell commands.
- `beforeMCPExecution` / `afterMCPExecution` — control MCP tool usage.
- `beforeReadFile` / `afterFileEdit` — control file access and edits.
- `beforeSubmitPrompt` — validate prompts before submission.
- `preCompact` — observe context window compaction.
- `stop` — handle agent completion.
- `afterAgentResponse` / `afterAgentThought` — track agent responses.

### Tab hooks (inline completions)

These fire for autonomous Tab operations:

- `beforeTabFileRead` — control file access for Tab completions.
- `afterTabFileEdit` — post-process Tab edits.

### App lifecycle hooks

These fire outside any agent session:

- `workspaceOpen` — fires when Cursor opens a workspace and on every workspace folder change.
  Can return additional plugin paths to load for the current workspace.
  The docs state: "Runs in the Cursor desktop app and CLI."

## Hook events index

Filenames follow the convention `camelCaseEventName` -> `lowercase-hyphenated-slug.md`.
Per-event files are written by other agents and are not part of this assignment; the table below documents the intended mapping.

| Hook event              | Category      | File                              |
|--------------------------|---------------|-------------------------------------|
| `sessionStart`            | Agent hooks   | `session-start.md`                  |
| `sessionEnd`               | Agent hooks   | `session-end.md`                    |
| `preToolUse`               | Agent hooks   | `pre-tool-use.md`                   |
| `postToolUse`              | Agent hooks   | `post-tool-use.md`                  |
| `postToolUseFailure`       | Agent hooks   | `post-tool-use-failure.md`          |
| `subagentStart`            | Agent hooks   | `subagent-start.md`                 |
| `subagentStop`             | Agent hooks   | `subagent-stop.md`                  |
| `beforeShellExecution`     | Agent hooks   | `before-shell-execution.md`         |
| `afterShellExecution`      | Agent hooks   | `after-shell-execution.md`          |
| `beforeMCPExecution`       | Agent hooks   | `before-mcp-execution.md`           |
| `afterMCPExecution`        | Agent hooks   | `after-mcp-execution.md`            |
| `beforeReadFile`           | Agent hooks   | `before-read-file.md`               |
| `afterFileEdit`            | Agent hooks   | `after-file-edit.md`                |
| `beforeSubmitPrompt`       | Agent hooks   | `before-submit-prompt.md`           |
| `preCompact`               | Agent hooks   | `pre-compact.md`                    |
| `stop`                     | Agent hooks   | `stop.md`                           |
| `afterAgentResponse`       | Agent hooks   | `after-agent-response.md`           |
| `afterAgentThought`        | Agent hooks   | `after-agent-thought.md`            |
| `beforeTabFileRead`        | Tab hooks     | `before-tab-file-read.md`           |
| `afterTabFileEdit`         | Tab hooks     | `after-tab-file-edit.md`            |
| `workspaceOpen`            | App lifecycle | `workspace-open.md`                 |

## Surface availability summary

The source page does not state, per event, whether it runs in the desktop app versus the CLI; the only explicit per-surface statement on the page is for `workspaceOpen`: "Runs in the Cursor desktop app and CLI."
For all other agent and tab hooks, the page distinguishes only "local" execution (desktop app and CLI together, undifferentiated) from cloud agent execution, via the Cloud agent support section's "Supported hooks" and "Hooks not available in cloud agents" lists.
Where the page leaves a cell unstated, it is marked "not documented" below rather than inferred.

| Hook event              | Desktop app       | CLI               | Cloud agent      |
|---------------------------|--------------------|--------------------|--------------------|
| `sessionStart`             | not documented     | not documented     | not available       |
| `sessionEnd`                | not documented     | not documented     | not available       |
| `preToolUse`                | not documented     | not documented     | supported            |
| `postToolUse`               | not documented     | not documented     | supported            |
| `postToolUseFailure`        | not documented     | not documented     | supported            |
| `subagentStart`             | not documented     | not documented     | supported            |
| `subagentStop`              | not documented     | not documented     | supported            |
| `beforeShellExecution`      | not documented     | not documented     | supported            |
| `afterShellExecution`       | not documented     | not documented     | supported            |
| `beforeMCPExecution`        | not documented     | not documented     | not available       |
| `afterMCPExecution`         | not documented     | not documented     | not available       |
| `beforeReadFile`            | not documented     | not documented     | supported            |
| `afterFileEdit`             | not documented     | not documented     | supported            |
| `beforeSubmitPrompt`        | not documented     | not documented     | supported            |
| `preCompact`                | not documented     | not documented     | supported            |
| `stop`                      | not documented     | not documented     | supported            |
| `afterAgentResponse`        | not documented     | not documented     | supported            |
| `afterAgentThought`         | not documented     | not documented     | supported            |
| `beforeTabFileRead`         | not documented     | not documented     | not available       |
| `afterTabFileEdit`          | not documented     | not documented     | not available       |
| `workspaceOpen`             | yes (stated)        | yes (stated)        | not available       |

The docs state: "Some hooks don't apply to cloud agents due to differences in the execution environment", and give a per-hook reason for each in a table (`sessionStart` and `beforeMCPExecution`/`afterMCPExecution` cite the cloud agent's read-only startup phase specifically).
See `cloud-agents.md` for the full supported/unavailable lists and configuration-source detail.
