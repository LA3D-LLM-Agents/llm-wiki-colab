"""Native installation into each harness's isolated state root."""

import shutil


def install_claude(run, case, marketplace, plugin, marketplace_name):
    probe = run.root / case
    run.command(f"{case}-marketplace", ["plugin", "marketplace", "add", str(marketplace)], probe)
    run.command(f"{case}-install", ["plugin", "install", f"{plugin.name}@{marketplace_name}"], probe)


def install_codex(run, case, marketplace, plugin, marketplace_name):
    probe = run.root / case
    run.command(f"{case}-marketplace", ["plugin", "marketplace", "add", str(marketplace)], probe)
    run.command(f"{case}-install", ["plugin", "add", f"{plugin.name}@{marketplace_name}"], probe)


def install_cursor(run, case, marketplace, plugin, marketplace_name):
    # Exercise the installed-plugin loader with a copy. The isolation wrapper
    # preserves this caller-owned root while blocking account plugin downloads.
    shutil.copytree(plugin, run.root / case / "home/.cursor/plugins/local" / plugin.name)


def install_built_plugin(run, case, marketplace, *, plugin_name="llm-wiki", marketplace_name="llm-wiki-colab"):
    plugin = marketplace / run.harness / "plugins" / plugin_name
    installer = {"claude": install_claude, "codex": install_codex, "cursor": install_cursor}[run.harness]
    run.report["loading"] = ("built artifact copied into isolated Cursor local plugins" if run.harness == "cursor"
                             else "built artifact installed through local marketplace")
    run.report["phase"] = f"{case}-install"
    run.save()
    installer(run, case, marketplace, plugin, marketplace_name)


def install_fixture(run, case, fixture):
    """Prepare a synthetic plugin and return any session directory override."""
    run.report["loading"] = "local marketplace install" if run.harness == "codex" else "--plugin-dir"
    run.save()
    if run.harness == "codex":
        install_codex(run, case, fixture.marketplace, fixture.path, "metadata-market")
        return None
    return fixture.path
