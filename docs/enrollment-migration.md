# Structured enrollment migration

The shared `wiki-enroll` source now emits transitional cards: validated schema-1.0
`x-fabric-card` plus matching legacy identity, description and capability fields.
Assembly emits the same helper/schema for Claude, Codex and Cursor. The source
skill's existing explicit-invocation policy is retained.

Runtime contract and examples live in
[the skill reference](../plugins/llm-wiki/skills/wiki-enroll/references/enrollment.md).
Generation derives the publication filename and default new identity from the
host GitHub origin. Existing identities, structured skill IDs, body text and
unrelated frontmatter survive updates. Updates require `--update`; unsupported
schema versions or conflicting representations stop before writing. Drafts do not
publish or add topics automatically. GitHub registration requires `--add-topic`.

## Validation — 2026-10-01

Against scratch assembly output, 20 enrollment behavior tests passed under system
Python 3.9.6; all three emitted helpers were identical and exercised without a
harness-root environment variable. Tests cover punctuation, EOF, noninteractive
inputs, alternate attachment paths, remote checks, identity/body/skill preservation,
rejected updates, concurrent edits, isolated staging and topic failures. Skill
validation, Ruff and shell syntax checks passed.

The complete behavior runner was exercised with `TMPDIR=/private/tmp` to avoid
an existing macOS `/var` versus `/private/var` path assertion in initializer tests.
After installing git-cliff 2.14.2, the complete runner passed with zero failing
test files for version 0.5.0. The opt-in Cursor model smoke was skipped.

An offline check in the fabric repository
(`docs/agent-card-migration/check_enrollment.py`) ran built enrollment for a new
card, a legacy migration, and a structured update through the actual upgraded
index projector and fabric importer/SHACL mapper. All three passed; the legacy
identity and custom prose were retained. No real card, topic, wiki commit or
publication was performed by those checks.

## Release boundary

This is development work on a branch based on `src`; `main` remains generated
output. Version 0.5.0 is prepared with passing release gates. Publish using the
repository's build/publish workflow, which builds and verifies the committed
source. Do not hand-edit or force-push `main`.

Publish compatible federation/fabric readers and upgrade connector runtimes before
publishing migrated cards. The helper can prepare local drafts independently.
A local card, a registered topic, and verified federation inclusion are distinct
outcomes. Enrollment success does not prove a live invocation route.
