"""Pytest fixtures and explicit opt-in for model calls."""

from pathlib import Path
import shutil
import tempfile

import pytest

from .harness_support import HarnessRun, credentials


def pytest_addoption(parser):
    group = parser.getgroup("harness capabilities")
    group.addoption("--run-live", action="store_true", help="allow paid model sessions")
    group.addoption("--harness", choices=("all", "claude", "codex", "cursor"), default="all")
    group.addoption("--model", help="model override; requires --harness with one harness")
    group.addoption("--keep", action="store_true", help="retain private captures")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: makes model calls; requires --run-live")
    config.addinivalue_line("markers", "capability: runs an external harness CLI")
    if config.getoption("--model") and config.getoption("--harness") == "all":
        raise pytest.UsageError("--model requires --harness claude, codex, or cursor")


def pytest_collection_modifyitems(config, items):
    selected, deselected = [], []
    for item in items:
        harness = getattr(item, "callspec", None)
        harness = harness.params.get("harness") if harness else None
        if harness and config.getoption("--harness") not in ("all", harness):
            deselected.append(item)
            continue
        if item.get_closest_marker("live") and not config.getoption("--run-live"):
            item.add_marker(pytest.mark.skip(reason="model calls require --run-live"))
        selected.append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    run = item.funcargs.get("harness_run")
    if run and report.when == "call":
        run.report["status"] = report.outcome
        if report.failed:
            run.report["failure"] = str(call.excinfo.value)
        run.save()


@pytest.fixture
def harness_run(request, harness):
    auth, reason = credentials(harness)
    if reason:
        pytest.skip(reason)
    # Keep probe ancestors clear of project instructions; pytest's tmp_path
    # location can be configured inside a checkout.
    root = Path(tempfile.mkdtemp(prefix="skill-capability-", dir="/tmp"))
    run = None
    try:
        run = HarnessRun(root, harness, auth, request.config.getoption("--model"))
        yield run
    finally:
        if request.config.getoption("--keep"):
            print(f"Private captures retained: {root}")
        else:
            shutil.rmtree(root)
