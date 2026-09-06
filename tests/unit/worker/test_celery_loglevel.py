"""Maps BunkerWeb's NGINX-style LOG_LEVEL vocabulary to Celery's --loglevel choices.

Celery's --loglevel only accepts DEBUG/INFO/WARNING/ERROR/CRITICAL/FATAL and exits
immediately on anything else, so LOG_LEVEL=notice (a perfectly ordinary BunkerWeb
value) used to kill the worker before a single job ran.
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "src" / "worker" / "celery-loglevel.sh"


def _run(*args):
    return subprocess.run(["sh", str(SCRIPT), *args], capture_output=True, text=True, check=True)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("emerg", "CRITICAL"),
        ("alert", "CRITICAL"),
        ("crit", "CRITICAL"),
        ("error", "ERROR"),
        ("warn", "WARNING"),
        ("warning", "WARNING"),
        ("notice", "INFO"),
        ("info", "INFO"),
        ("debug", "DEBUG"),
        # Already-accepted Celery values must pass through unchanged (case-insensitive).
        ("critical", "CRITICAL"),
        ("fatal", "FATAL"),
        ("NOTICE", "INFO"),
        ("Debug", "DEBUG"),
        ("WARNING", "WARNING"),
    ],
)
def test_maps_known_levels(value, expected):
    result = _run(value)
    assert result.stdout.strip() == expected
    assert result.stderr == ""


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK), "the all-in-one image ships the tracked mode (Dockerfile:254 excludes *.sh)"


def test_default_is_info_with_no_argument():
    result = _run()
    assert result.stdout.strip() == "INFO"


def test_unknown_value_falls_back_to_info_with_a_warning():
    result = _run("bogus")
    assert result.stdout.strip() == "INFO"
    assert "bogus" in result.stderr
