# Cursor Hooks: Cloud Agent Support

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

## Supported hooks

The following hooks are supported for cloud agents:

`beforeShellExecution`, `afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeSubmitPrompt`, `preCompact`, `afterAgentResponse`, `afterAgentThought`, `stop`.

## Hooks not available in cloud agents

`sessionStart`, `sessionEnd`, `beforeMCPExecution`/`afterMCPExecution`, `beforeTabFileRead`/`afterTabFileEdit`, `workspaceOpen`.

The docs state: "Some hooks don't apply to cloud agents due to differences in the execution environment."
Individual reasons vary by hook: `sessionStart` and `beforeMCPExecution`/`afterMCPExecution` are deferred because cloud agents can still start in a read-only environment where hooks don't load; `sessionEnd` and `workspaceOpen` are tied to IDE/editor lifecycle boundaries that cloud agents lack; `beforeTabFileRead`/`afterTabFileEdit` don't apply because Tab completions are an IDE feature.

## Configuration sources

Cloud agents load hooks from project hooks (`.cursor/hooks.json`), team hooks, and enterprise hooks.
User-level hooks (`~/.cursor/hooks.json`) are unavailable in cloud agents.

## Execution type limits

Cloud agents run **command-based hooks** only.
Prompt-based hooks require authentication wiring between the hook and the agent loop, which isn't available in the cloud execution environment.
