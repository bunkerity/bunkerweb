"""update-check's exit codes, executed rather than read.

A GitHub rate limit at stack start used to log two ❌ lines and fail the AIO ``db`` CI arm
(run 32989964850): the job exited 2 for a transient, non-actionable network failure, and its own
``sys_exit`` was then swallowed by ``except BaseException`` and relabeled a crash. These tests run
the shipped script with stubbed deps and pin the contract:

* a ``RequestException`` from the GitHub call is a WARNING and exit 0 — a missed release check is
  not a job failure, the next run retries;
* an unexpected exception still exits 2 with an error — the transient branch must not become a
  blanket swallow;
* ``SystemExit`` raised inside the try block keeps its own code instead of being converted to 2.
"""

import runpy
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_FILE = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "update-check.py"


class _Logger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def info(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, msg, *a, **k):
        self.warnings.append(str(msg))

    def error(self, msg, *a, **k):
        self.errors.append(str(msg))


def _run(monkeypatch, get_behavior):
    """Execute the shipped script with stubbed deps; return (exit_code, logger)."""
    logger = _Logger()

    logger_mod = types.ModuleType("logger")
    logger_mod.getLogger = lambda name: logger

    jobs_mod = types.ModuleType("jobs")

    class Job:
        def __init__(self, *a, **k):
            pass

        def get_cache(self, *a, **k):
            return None

        def cache_file(self, *a, **k):
            return True, ""

    jobs_mod.Job = Job

    common_utils_mod = types.ModuleType("common_utils")
    common_utils_mod.get_version = lambda: "1.7.0"
    common_utils_mod.is_newer_version_available = lambda cur, latest: False

    import requests

    requests_mod = types.ModuleType("requests")
    requests_mod.get = get_behavior
    requests_mod.exceptions = requests.exceptions

    for name, mod in (("logger", logger_mod), ("jobs", jobs_mod), ("common_utils", common_utils_mod), ("requests", requests_mod)):
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.delitem(sys.modules, "requests.exceptions", raising=False)
    monkeypatch.setitem(sys.modules, "requests.exceptions", requests.exceptions)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(JOB_FILE), run_name="__main__")
    return excinfo.value.code, logger


def test_a_github_request_failure_is_a_warning_and_exit_zero(monkeypatch):
    import requests

    def raise_request_exception(*a, **k):
        raise requests.exceptions.HTTPError("403 Client Error: rate limit exceeded")

    code, logger = _run(monkeypatch, raise_request_exception)
    assert code == 0
    assert any("GitHub" in w for w in logger.warnings)
    assert logger.errors == []


def test_an_unexpected_exception_still_exits_two(monkeypatch):
    def raise_value_error(*a, **k):
        raise ValueError("not a network problem")

    code, logger = _run(monkeypatch, raise_value_error)
    assert code == 2
    assert logger.errors


def test_no_stable_release_exits_two_with_a_single_error(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return []

    code, logger = _run(monkeypatch, lambda *a, **k: _Resp())
    assert code == 2
    # SystemExit must keep its own code and not be relabeled a crash by the outer handler,
    # which used to add a second ❌ line ("Exception while running update-check.py : 2").
    assert logger.errors == ["Failed to fetch latest release information"]
