"""Pytest fixtures and explicit opt-in for model calls."""

from pathlib import Path
from collections import Counter
import shutil
import tempfile
import subprocess

import pytest

from .harness_support import REPO, HarnessRun, credentials, write_json


def pytest_addoption(parser):
    group = parser.getgroup("harness capabilities")
    group.addoption("--run-live", action="store_true", help="allow paid model sessions")
    group.addoption("--harness", choices=("all", "claude", "codex", "cursor"), default="all")
    group.addoption("--model", help="model override; requires --harness with one harness")
    group.addoption("--keep", action="store_true", help="retain private captures")
    group.addoption("--run-non-deterministic", action="store_true", help="allow model-sensitive evaluations")
    group.addoption("--resource-samples", type=int, default=1, help="independent bundled-resource attempts per harness")


def pytest_configure(config):
    config._resource_results = []
    config.addinivalue_line("markers", "live: makes model calls; requires --run-live")
    config.addinivalue_line("markers", "capability: runs an external harness CLI")
    config.addinivalue_line("markers", "integration: exercises the assembled llm-wiki plugin")
    config.addinivalue_line("markers", "non_deterministic: model-sensitive evaluation; requires explicit model and opt-in")
    if config.getoption("--resource-samples") < 1:
        raise pytest.UsageError("--resource-samples must be positive")
    if config.getoption("--model") and config.getoption("--harness") == "all":
        raise pytest.UsageError("--model requires --harness claude, codex, or cursor")


def pytest_generate_tests(metafunc):
    if "resource_sample" in metafunc.fixturenames:
        metafunc.parametrize("resource_sample", range(1, metafunc.config.getoption("--resource-samples") + 1))


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
        if item.get_closest_marker("non_deterministic"):
            if not config.getoption("--run-non-deterministic"):
                item.add_marker(pytest.mark.skip(reason="evaluation requires --run-non-deterministic"))
            elif not config.getoption("--model"):
                item.add_marker(pytest.mark.skip(reason="evaluation requires explicit --harness and --model"))
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
            if item.get_closest_marker("non_deterministic"):
                run.report.setdefault("evaluation_outcome", "infrastructure_failure")
        run.save()
        if item.get_closest_marker("non_deterministic"):
            item.config._resource_results.append({
                "test": item.nodeid, "harness": run.harness,
                "model": run.report.get("model"), "version": run.report.get("version"),
                "outcome": run.report.get("evaluation_outcome", "infrastructure_failure"),
                "captures": str(run.root),
            })


def pytest_terminal_summary(terminalreporter, config):
    results = config._resource_results
    if not results:
        return
    counts = Counter(result["outcome"] for result in results)
    assessed = len(results) - counts["infrastructure_failure"]
    successes = counts["first_attempt_success"]
    root = Path(tempfile.mkdtemp(prefix="resource-evaluation-", dir="/tmp"))
    write_json(root / "summary.json", {"attempts": results, "counts": dict(counts),
                                       "first_attempt_successes": successes, "assessed_attempts": assessed})
    terminalreporter.write_sep("=", "non-deterministic resource evaluation")
    terminalreporter.write_line(str(dict(counts)))
    terminalreporter.write_line(f"First-attempt successes: {successes}/{assessed} assessed attempts; infrastructure failures reported separately")
    terminalreporter.write_line(f"Summary and capture locations: {root / 'summary.json'}")


@pytest.fixture
def built_marketplace(harness_run):
    """Build the artifact without consulting repository state or real remotes."""
    run = harness_run
    output = run.root / "built"
    with (run.root / "build.log").open("w") as log:
        subprocess.run(["uv", "run", str(REPO / "build/assemble.py"), "--out", str(output),
                        "--owner-repo", "LA3D-LLM-Agents/llm-wiki-colab",
                        "--source-ref", "0" * 40], check=True, stdout=log, stderr=subprocess.STDOUT)
    return output


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
        if request.config.getoption("--keep") or request.node.get_closest_marker("non_deterministic"):
            print(f"Private captures retained: {root}")
        else:
            shutil.rmtree(root)
