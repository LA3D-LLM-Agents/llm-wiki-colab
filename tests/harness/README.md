# Harness capability probes

Run skill metadata delivery independently of `tests/run.sh`:

```sh
python3 tests/harness/test_skill_metadata.py codex
python3 tests/harness/test_skill_metadata.py claude
python3 tests/harness/test_skill_metadata.py cursor
```

`all` runs all three. Claude and Cursor each spend two model calls: one without
the fixture plugin and one with it. Codex uses local `debug prompt-input` output,
so its result establishes rendered-prompt inclusion, not a completed model call.
Claude defaults to `haiku`; Cursor uses its harness default. `--model NAME`
overrides the model for a single live harness.

Each probe uses `scripts/isolated-<harness>.sh`, a clean `/tmp` workspace, and
separate state roots for the absent/present cases. The wrappers currently require
credentials even for Codex's local inspection. Missing CLI or credentials is a
skip, not a pass. Exit codes: 0 for no failures and at least one pass, 1 for any
failure, 77 when everything was skipped.

The fixture is a minimal native plugin with one skill. Its random name and
description marker never appear in the user prompt. The body carries a third
marker, which must not appear in the response. Live probes require name and
description marker recovery and audit the recorded conversation for tool use;
Tools remain registered: removing Claude's Skill tool can also remove the
metadata being tested. The prompt prohibits tool use, and the audit enforces
this for both live harnesses. Cursor's ask mode alone does not prohibit reads.
Missing audit evidence fails the probe.
The negative control must produce nonempty output without either identifier.

This measures metadata delivery only. It does not invoke the skill, test skill
selection or instruction compliance, or establish that the built llm-wiki plugin
is correctly packaged. The fixture deliberately omits optional frontmatter such
as `disable-model-invocation`; those variations need separate cases.

Use `--keep` to retain captures and `results.json` for investigation. Captures
can contain account context, identity, and full API bodies; keep them private.
Without `--keep`, scratch data is removed on completion, including failures.
Auth copies are removed by the wrappers after each command. Ctrl-C lets wrapper
signal cleanup run; forcibly killing the process can leave scratch data behind.

The existing `cursor/test_session_context.sh` is a separate session-start delivery
probe. Isolation canaries in `scripts/isolated-*.test.sh` test the wrappers
themselves and are also explicitly invoked.

Run the evidence-parser checks without CLIs, credentials, or model calls:

```sh
python3 -B -m unittest discover -s tests/harness -p test_skill_metadata_audit.py
```
