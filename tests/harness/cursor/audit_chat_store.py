#!/usr/bin/env python3
"""Summarize a cursor-agent chat store for the harness conformance tests.

Usage: audit_chat_store.py <store.db> <nonce>

Probed on cursor-agent 2026.08.25-3e8eec8: the conversation record of a -p
run is a SQLite blob store (CURSOR_CONFIG_DIR/chats/<hash>/<chat-id>/
store.db).  Blobs starting with "{" are role-tagged messages
({"role": ..., "content": ...}); assistant content is a JSON-encoded array
of typed parts (reasoning, text, tool-*).  Non-JSON blobs are internal and
skipped.

Prints three fact lines for the caller to assert on:
  nonce_roles=<roles of messages containing the nonce>
  roles=<all message roles seen>
  part_types=<all content part types seen>
"""

import json
import sqlite3
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    store, nonce = sys.argv[1], sys.argv[2]
    nonce_roles, roles, part_types = set(), set(), set()
    for (data,) in sqlite3.connect(store).execute("SELECT data FROM blobs"):
        if not data.startswith(b"{"):
            continue
        msg = json.loads(data)
        role = msg.get("role", "?")
        roles.add(role)
        content = msg.get("content")
        if isinstance(content, str) and content.startswith("["):
            content = json.loads(content)
        if isinstance(content, list):
            part_types.update(p.get("type", "?") for p in content)
        if nonce in json.dumps(msg):
            nonce_roles.add(role)
    print("nonce_roles=" + ",".join(sorted(nonce_roles)))
    print("roles=" + ",".join(sorted(roles)))
    print("part_types=" + ",".join(sorted(part_types)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
