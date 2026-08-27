"""The every-page apply-failure banner uses the pending-change gate, not its inverse."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

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
    )

    matching = [call for call in flashes.call_args_list if "could not be applied" in call.args[0]]
    assert bool(matching) is expected
    if matching:
        assert "/jobs" in matching[0].args[0]
        assert matching[0].args[1] == "error"
