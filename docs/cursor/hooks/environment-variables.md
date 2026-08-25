# Cursor Hooks Environment Variables

Source: https://cursor.com/docs/hooks (retrieved 2026-08-25).

Environment variables available to hook scripts:

| Variable                  | Description                                                    | Always present         |
|------------------------------|--------------------------------------------------------------------|---------------------------|
| `CURSOR_PROJECT_DIR`           | Workspace root directory.                                             | Yes                          |
| `CURSOR_VERSION`               | Cursor version string.                                                | Yes                          |
| `CURSOR_USER_EMAIL`            | Authenticated user email.                                             | If logged in                 |
| `CURSOR_TRANSCRIPT_PATH`       | Path to the conversation transcript file.                              | If transcripts enabled        |
| `CURSOR_CODE_REMOTE`           | Set to the string `"true"` when running in a remote workspace.          | For remote workspaces         |
| `CLAUDE_PROJECT_DIR`           | Alias for project dir (Claude compatibility).                          | Yes                          |

## Session-scoped variables

Session-scoped environment variables from `sessionStart` hooks are passed to all subsequent hook executions within that session.
This means hooks can dynamically inject custom environment variables through the `sessionStart` hook's output, which then become available to later hooks in the same session.
