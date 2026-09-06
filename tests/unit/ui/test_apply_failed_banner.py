"""The every-page apply-failure banner uses the pending-change gate, not its inverse.

Also covers the deferred-run branch added alongside it (PO ruling 2026-09-02): a push-configs run
that left the change flags pending on purpose (``success=True``, ``error`` prefixed
``JOB_DEFERRAL_PREFIX``, see ``src/common/utils/jobs.py``) must flash a distinct, non-alarming
"warning" notice rather than either the real-failure "error" banner or silence.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jobs import JOB_DEFERRAL_PREFIX  # type: ignore — src/common/utils on sys.path, see tests/unit/conftest.py

MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"


def _status_banner_branch():
    """Execute the real banner branch without importing main.py's container boot process."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    before_request = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "before_request")
    outer = next(
        node
        for node in ast.walk(before_request)
        if isinstance(node, ast.If)
        and "request.path.startswith('/loading')" in ast.unparse(node.test)
        and "current_user.is_authenticated" in ast.unparse(node.test)
    )
    function = ast.FunctionDef(
        name="run_status_banner",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg=name)
                for name in (
                    "changes_ongoing",
                    "metadata",
                    "DATA",
                    "request",
                    "current_user",
                    "flask_flash",
                    "flash",
                    "url_for",
                    "API_CLIENT",
                    "ApiClientError",
                    "ApiUnavailableError",
                    "LOGGER",
                    "translated",
                    "JOB_DEFERRAL_PREFIX",
                )
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[outer],
        decorator_list=[],
    )
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(MAIN), "exec"), namespace)
    return namespace["run_status_banner"]


@pytest.mark.parametrize(
    ("changes_ongoing", "last_run", "expected"),
    (
        (True, {"success": False}, True),
        (True, {"success": True}, False),
        (False, {"success": False}, False),
        (True, ConnectionError("API unavailable"), False),
    ),
)
def test_apply_failed_banner_truth_table(changes_ongoing, last_run, expected):
    flashes = Mock()
    api_client = Mock()
    if isinstance(last_run, Exception):
        api_client.get_last_job_run.side_effect = last_run
    else:
        api_client.get_last_job_run.return_value = last_run

    _status_banner_branch()(
        changes_ongoing,
        {"failover": False},
        {"CONFIG_CHANGED": False},
        SimpleNamespace(path="/home"),
        SimpleNamespace(is_authenticated=True),
        flashes,
        flashes,
        lambda endpoint: "/jobs" if endpoint in {"jobs", "jobs.jobs_page"} else f"/{endpoint}",
        api_client,
        RuntimeError,
        ConnectionError,
        Mock(),
        lambda key: None,
        JOB_DEFERRAL_PREFIX,
    )

    matching = [call for call in flashes.call_args_list if "could not be applied" in call.args[0]]
    assert bool(matching) is expected
    if matching:
        assert "/jobs" in matching[0].args[0]
        assert matching[0].args[1] == "error"


@pytest.mark.parametrize(
    ("last_run", "expect_deferred_flash"),
    (
        ({"success": True, "error": f"{JOB_DEFERRAL_PREFIX}All 2 registered BunkerWeb instance(s) are down"}, True),
        ({"success": True, "error": None}, False),  # plain success, nothing pending
        ({"success": False, "error": f"{JOB_DEFERRAL_PREFIX}looks deferred but isn't"}, False),  # a crash always wins
    ),
)
def test_deferred_run_flashes_a_distinct_warning(last_run, expect_deferred_flash):
    """A deferred push-configs run is neither a failure nor silence: it gets its own non-alarming
    "warning" notice. Mutation proof: deleting the ``elif changes_ongoing and
    last_push_configs_deferred:`` branch from src/ui/main.py turns the first row's assertion red
    (no call contains "not applied yet" any more) while leaving the other two green -- confirmed by
    hand before this test was written, not asserted here since the branch under test is exec'd
    fresh from the live source on every run.
    """
    flashes = Mock()
    api_client = Mock()
    api_client.get_last_job_run.return_value = last_run

    _status_banner_branch()(
        True,  # changes_ongoing
        {"failover": False},
        {"CONFIG_CHANGED": False},
        SimpleNamespace(path="/home"),
        SimpleNamespace(is_authenticated=True),
        flashes,
        flashes,
        lambda endpoint: "/jobs" if endpoint in {"jobs", "jobs.jobs_page"} else f"/{endpoint}",
        api_client,
        RuntimeError,
        ConnectionError,
        Mock(),
        lambda key: None,
        JOB_DEFERRAL_PREFIX,
    )

    deferred_calls = [call for call in flashes.call_args_list if "not applied yet" in call.args[0]]
    failed_calls = [call for call in flashes.call_args_list if "could not be applied" in call.args[0]]

    assert bool(deferred_calls) is expect_deferred_flash
    if deferred_calls:
        assert "/jobs" in deferred_calls[0].args[0]
        assert deferred_calls[0].args[1] == "warning"
    # A deferred flash and a failed flash are mutually exclusive -- the crash row above must land
    # in "could not be applied" (already covered by the truth table), never in both.
    assert not (deferred_calls and failed_calls)
