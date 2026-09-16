"""Auth runs after selection and before any test body, without real model calls."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture
def run_suite(tmp_path):
    source = Path(__file__).parent
    suite = tmp_path / "tests" / "harness"
    suite.mkdir(parents=True)
    for path in source.glob("*.py"):
        if not path.name.startswith("test_") or path.name == "test_conversation.py":
            shutil.copy(path, suite / path.name)
    shutil.copy(source / "pytest.ini", suite / "pytest.ini")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    probe = scripts / "check-harness-auth.sh"
    probe.write_text(f"#!{sys.executable}\n" + '''
import os, sys
with open(os.environ["AUTH_TEST_EVENTS"], "a") as log:
    log.write("auth:" + ",".join(sys.argv[1:]) + "\\n")
print("recorded auth probe")
sys.exit(int(os.environ["AUTH_TEST_EXIT"]))
''')
    probe.chmod(0o755)
    (suite / "test_cases.py").write_text('''
import os
import pytest

def record(event):
    with open(os.environ["AUTH_TEST_EVENTS"], "a") as log:
        log.write(event + "\\n")

def test_offline():
    record("offline")

@pytest.mark.live
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_live(harness):
    record("live:" + harness)

@pytest.mark.live
@pytest.mark.parametrize("harness", ["codex"])
def test_live_again(harness):
    record("again:" + harness)

@pytest.mark.live
@pytest.mark.non_deterministic
@pytest.mark.parametrize("harness", ["cursor"])
def test_evaluation(harness):
    record("evaluation:" + harness)
''')

    def run(*args, auth_exit=0, filename="test_cases.py"):
        events = tmp_path / "events"
        events.write_text("")
        env = dict(os.environ, PYTEST_ADDOPTS="", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                   AUTH_TEST_EVENTS=str(events), AUTH_TEST_EXIT=str(auth_exit))
        result = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", str(suite / filename), "-q", *args],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
        )
        return result, events.read_text().splitlines()

    return run


@pytest.mark.parametrize("args,expected", [
    (("--run-live", "--collect-only"), []),
    (("--run-live", "-m", "not live"), ["offline"]),
    ((), ["offline"]),
    (("--run-live", "-k", "test_live", "--harness", "codex"),
     ["auth:codex", "live:codex", "again:codex"]),
    (("--run-live", "-k", "test_live and codex"),
     ["auth:codex", "live:codex", "again:codex"]),
    (("--run-live", "-k", "test_live"),
     ["auth:claude,codex,cursor", "live:claude", "live:codex", "live:cursor", "again:codex"]),
    (("--run-live", "-k", "test_evaluation"), []),
    (("--run-live", "-k", "test_evaluation", "--run-non-deterministic",
      "--harness", "cursor", "--model", "probe"),
     ["auth:cursor", "evaluation:cursor"]),
])
def test_auth_follows_selection(run_suite, args, expected):
    result, events = run_suite(*args)
    assert result.returncode == 0, result.stdout + result.stderr
    assert events == expected


def test_auth_failure_stops_test_bodies(run_suite):
    result, events = run_suite("--run-live", "--harness", "codex", auth_exit=1)
    assert result.returncode == 2, result.stdout + result.stderr
    assert events == ["auth:codex"]
    assert "every selected harness signed in" in result.stdout + result.stderr


def test_real_offline_cases_do_not_require_auth(run_suite):
    result, events = run_suite("--run-live", auth_exit=1, filename="test_conversation.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout
    assert events == []
