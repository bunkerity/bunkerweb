"""UB2-4: execute CI engine steps with controlled pytest output and exit status."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("step_name", ["Run unit tests (all engines)", "Run the DB-layer unit tests (MySQL)"])
@pytest.mark.parametrize(
    "output,code,expected",
    [
        ("14 skipped", 0, 1),
        ("100 passed, 14 skipped\nSKIPPED postgresql not configured (set BW_TEST_PG_URI)", 0, 1),
        ("100 passed, 14 skipped\nSKIPPED mariadb not reachable at local test database", 0, 1),
        ("100 passed", 1, 1),
        ("100 passed, 2 skipped\nSKIPPED optional tool is unavailable", 0, 0),
    ],
)
def test_engine_step_rejects_empty_unavailable_or_failed_run(tmp_path, step_name, output, code, expected):
    workflow = yaml.safe_load((ROOT / ".github/workflows/unit-tests.yml").read_text())
    script = next(step["run"] for step in workflow["jobs"]["matrix"]["steps"] if step["name"] == step_name)
    # Keep the real step's shell, pipefail, tee and guards; substitute only pytest/timeout.
    executable = tmp_path / "pytest"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$CI_TEST_OUTPUT"\nexit "$CI_TEST_CODE"\n')
    executable.chmod(0o755)
    timeout = tmp_path / "timeout"
    timeout.write_text('#!/bin/sh\nshift 3\nexec "$@"\n')
    timeout.chmod(0o755)
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=tmp_path,
        env=os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}", "CI_TEST_OUTPUT": output, "CI_TEST_CODE": str(code)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert (result.returncode != 0) == bool(expected), result.stdout + result.stderr
