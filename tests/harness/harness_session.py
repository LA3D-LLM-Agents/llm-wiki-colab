"""Native session commands and response collection for isolated harnesses."""


def session_claude(run, case, prompt, session_id, *, plugin_dir, trust_hooks, writable):
    args = ["-p", "--session-id", session_id, "--model", run.resolved_model,
            "--max-budget-usd", "1"]
    if writable:
        args += ["--permission-mode", "acceptEdits"]
    if plugin_dir is not None:
        args += ["--plugin-dir", str(plugin_dir)]
    # The delimiter prevents variadic CLI options swallowing the prompt.
    return run.command(case, [*args, "--", prompt], run.root / case)


def session_codex(run, case, prompt, session_id, *, plugin_dir, trust_hooks, writable):
    last = run.root / f"{case}.last-message"
    args = ["exec", "--skip-git-repo-check", "-s", "workspace-write" if writable else "read-only",
            "-m", run.resolved_model, "-o", str(last)]
    if trust_hooks:
        args.append("--dangerously-bypass-hook-trust")
    run.command(case, [*args, prompt], run.root / case)
    return last.read_text()


def session_cursor(run, case, prompt, session_id, *, plugin_dir, trust_hooks, writable):
    args = ["-p", "--trust", "--sandbox", "disabled", "--output-format", "text"]
    args += ["--force"] if writable else ["--mode", "ask"]
    if run.model:
        args += ["--model", run.model]
    if plugin_dir is not None:
        args += ["--plugin-dir", str(plugin_dir)]
    return run.command(case, [*args, "--", prompt], run.root / case)
