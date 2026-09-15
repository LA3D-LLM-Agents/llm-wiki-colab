#!/usr/bin/env bash
# Orientation must surface the index and log that the wiki was initialized
# with. That name (`wiki-init --repo-name`, an origin renamed since init) need
# not match what the host repository's origin derives today, and other
# index_*.md pages in the wiki must not be mistaken for it.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/assert.sh"
require_env PLUGIN_ROOT

# mk_wiki <name> -> echoes a host repo whose .llm-wiki/ is initialized under <name>.
mk_wiki() {
    local root wiki
    root="$(mk_scratch git@github.com:example/host-repo.git)"
    wiki="$root/.llm-wiki"
    git -C "$root" init -q "$wiki"
    printf '# Index\n\n- [[experiment-7]] the page the model must see\n' > "$wiki/index_$1.md"
    printf '# Log\n\n## [2026-09-01] create | Wiki initialized\n## [2026-09-02] update | Recorded experiment 7\n' > "$wiki/log_$1.md"
    printf '# Schema\n' > "$wiki/SCHEMA_$1.md"
    echo "$root"
}

orientation() {
    (cd "$1" && python3 "$PLUGIN_ROOT/hooks/session-start.py") \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])'
}

root="$(mk_wiki lab-notes)"
git -C "$root/.llm-wiki" add -A
git -C "$root/.llm-wiki" -c user.name=t -c user.email=t@example.com commit -q -m "Initialize wiki foundations"
context="$(orientation "$root")"
assert_contains "$context" "the page the model must see" "orientation reads the wiki's index"
assert_contains "$context" "Recorded experiment 7" "orientation reads the wiki's log"
rm -rf "$root"

# With several index_*.md files only the initialized one carries the
# template's catalog line.
root="$(mk_wiki lab-notes)"
printf '# Index\n\nCatalog of all wiki pages, organized by category.\n\n- [[experiment-7]] the page the model must see\n' > "$root/.llm-wiki/index_lab-notes.md"
printf '# Index of experiments\n\n- [[experiment-9]] a decoy page the model must not see\n' > "$root/.llm-wiki/index_all-experiments.md"
git -C "$root/.llm-wiki" add -A
git -C "$root/.llm-wiki" -c user.name=t -c user.email=t@example.com commit -q -m "Initialize wiki foundations"
context="$(orientation "$root")"
assert_contains "$context" "the page the model must see" "orientation reads the initialized index beside a decoy"
assert_not_contains "$context" "a decoy page the model must not see" "orientation does not surface the decoy as the index"
rm -rf "$root"

exit "$ASSERT_FAIL"
