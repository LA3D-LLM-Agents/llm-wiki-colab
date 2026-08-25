# Manifest resolution per harness

Each harness reads its own catalog file and never consults the others' catalogs when its own is present.

| Harness     | Marketplace catalog                | Plugin manifest              |
| :---------- | :--------------------------------- | :--------------------------- |
| Claude Code | `.claude-plugin/marketplace.json`  | `.claude-plugin/plugin.json` |
| Codex       | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json`  |
| Cursor      | `.cursor-plugin/marketplace.json`  | `.cursor-plugin/plugin.json` |

## Codex fallback chains

Codex resolves manifests through fallback chains, trying each path in order and using the first that exists.

| Manifest    | Resolution order                                                                                                                                             |
| :---------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Marketplace | `.agents/plugins/marketplace.json` then `.agents/plugins/api_marketplace.json` then `.claude-plugin/marketplace.json` then `.cursor-plugin/marketplace.json` |
| Plugin      | `.codex-plugin/plugin.json` then `.claude-plugin/plugin.json` then `.cursor-plugin/plugin.json`                                                              |

The chains are defined in the codex-cli source at `core-plugins/src/marketplace.rs` (`MARKETPLACE_MANIFEST_RELATIVE_PATHS`) and `exec-server-protocol/src/protocol.rs` (`DISCOVERABLE_PLUGIN_MANIFEST_PATHS`), tag `rust-v0.145.0`.
They are undocumented behavior discovered through binary inspection and confirmed empirically.

Verified consequences (codex-cli 0.145.0):

- A repository containing only `.claude-plugin` manifests installs completely through `codex plugin marketplace add` and `codex plugin add`, and its skills reach the model prompt.
- When both manifests exist in one directory, the Codex-native one wins silently, so divergent copies produce divergent behavior with no warning.
- The fallback operates per directory: a plugin directory missing its native manifest falls back to a sibling manifest inside the same directory, never to a manifest in another directory.

## What the build does about it

Do not build the distribution layout on the fallbacks; emit a native manifest for every harness.

The silent-wins behavior is why the Codex emitter deletes `.claude-plugin/` from the Codex subtree.
If the Claude manifest rode along, `.codex-plugin/plugin.json` would win today, but any future path that consulted the stale Claude copy would diverge without a warning.

The Cursor emitter deletes `.claude-plugin/` from its subtree for the same reason.
Codex's plugin chain ends at `.cursor-plugin/plugin.json`, so the Cursor subtree is reachable by a fallback too, and a Claude manifest left beside the Cursor one is the same stale second copy.

The native manifests also carry fields only their own harness can express.
Codex requires a semver `version`, which is its entire install-cache key, and reads `interface.displayName` from the catalog.
Claude carries the marketplace `owner` block and resolves versions from commit SHAs.
