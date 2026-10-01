"""N-M4: the GitHub metadata refresh (LATEST_VERSION/GITHUB_STARS/PLUGIN_CATALOG) was absent for
up to an hour after every boot, with no log line.

Root cause: `on_starting` (gunicorn.conf.py) only ever fetches LATEST_VERSION at boot, but stamped
`LATEST_VERSION_LAST_CHECK` to "now" regardless -- the one key `before_request`'s hourly gate reads
to decide whether to run the *full* refresh (`update_github_metadata`, which is the only thing
that ever fetches GITHUB_STARS and PLUGIN_CATALOG). That pre-stamp suppressed the full refresh for
a full hour on every fresh boot, even though nothing had actually been fetched for those two keys
yet. Fixed by leaving the key out of the boot write, so `before_request`'s own epoch default lets
the first real request trigger the full refresh immediately, as it was clearly meant to.

Separately hardened for genuine (not boot-artifact) failures: `update_github_metadata` now retries
sooner than the steady hourly cadence after a fetch failure, with a bounded exponential backoff,
and logs the failure once (on the transition into the failing state) rather than staying silent
forever or re-warning every retry.

The modules pull in Flask/flask-login/qrcode/etc at import time, none of which the unit venv
carries, so the shipped definitions are spliced out of the source by name and executed here, as
`test_session_plumbing.py` does.
"""

import ast
from datetime import datetime, timedelta
from json import dumps, loads
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

_UI = Path(__file__).resolve().parents[3] / "src" / "ui"
MAIN = _UI / "main.py"
GUNICORN = _UI / "utils" / "gunicorn.conf.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(node for node in _tree(path).body if isinstance(node, ast.FunctionDef) and node.name == name)


# --------------------------------------------------------------------------------------- boot seed


def _boot_data_seed():
    """The slice of `on_starting` that writes ui_data.json, wrapped as a standalone function."""
    on_starting = _function(GUNICORN, "on_starting")
    start = next(
        i
        for i, node in enumerate(on_starting.body)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "latest_version"
    )
    end = next(i for i, node in enumerate(on_starting.body) if isinstance(node, ast.Expr) and "set_secure_permissions(UI_DATA_FILE)" in ast.unparse(node))
    function = ast.FunctionDef(
        name="seed_ui_data",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=name) for name in ("get_latest_stable_release", "api_client", "UI_DATA_FILE", "LOGGER", "set_secure_permissions")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=on_starting.body[start : end + 1],
        decorator_list=[],
    )
    namespace = {"dumps": dumps, "datetime": datetime}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(GUNICORN), "exec"), namespace)  # noqa: S102
    return namespace["seed_ui_data"]


def test_boot_seed_does_not_suppress_the_first_full_refresh():
    seed = _boot_data_seed()
    ui_data_file = Mock()

    seed(lambda: "1.7.0", SimpleNamespace(readonly=False), ui_data_file, Mock(), Mock())

    written = loads(ui_data_file.write_text.call_args.args[0])
    assert written["LATEST_VERSION"] == "1.7.0"
    # The presence of this key is exactly what suppressed `update_github_metadata` (and so
    # GITHUB_STARS/PLUGIN_CATALOG) for an hour after every boot -- it must stay absent.
    assert "LATEST_VERSION_LAST_CHECK" not in written


def test_boot_seed_survives_a_fetch_failure():
    seed = _boot_data_seed()
    ui_data_file = Mock()

    def boom():
        raise ConnectionError("no network")

    seed(boom, SimpleNamespace(readonly=False), ui_data_file, Mock(), Mock())

    written = loads(ui_data_file.write_text.call_args.args[0])
    assert written["LATEST_VERSION"] == "unknown"
    assert "LATEST_VERSION_LAST_CHECK" not in written


# --------------------------------------------------------------------------------- refresh backoff


def _update_github_metadata_namespace(fetchers):
    namespace = {"LOGGER": Mock(), "DATA": {}, "GITHUB_METADATA_REFRESH_SECONDS": 3600, "GITHUB_METADATA_RETRY_FLOOR_SECONDS": 60, **fetchers}
    function = _function(MAIN, "update_github_metadata")
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(MAIN), "exec"), namespace)  # noqa: S102
    return namespace


def _ok(value):
    return Mock(return_value=value)


def _boom():
    def raiser():
        raise ConnectionError("unreachable")

    return raiser


def test_a_failed_fetch_sets_the_retry_floor_and_warns_once():
    namespace = _update_github_metadata_namespace({"get_latest_stable_release": _boom(), "get_github_stars": _ok(42), "fetch_catalog": _ok(["x"])})

    namespace["update_github_metadata"]()

    assert namespace["DATA"]["GITHUB_METADATA_NEXT_RETRY_SECONDS"] == 60
    namespace["LOGGER"].warning.assert_called_once()


def test_repeated_failures_double_the_backoff_without_a_second_warning():
    namespace = _update_github_metadata_namespace({"get_latest_stable_release": _boom(), "get_github_stars": _boom(), "fetch_catalog": _boom()})

    namespace["update_github_metadata"]()
    namespace["update_github_metadata"]()
    namespace["update_github_metadata"]()

    assert namespace["DATA"]["GITHUB_METADATA_NEXT_RETRY_SECONDS"] == 240
    namespace["LOGGER"].warning.assert_called_once()


def test_the_backoff_is_bounded_at_the_steady_hourly_cadence():
    namespace = _update_github_metadata_namespace({"get_latest_stable_release": _boom(), "get_github_stars": _boom(), "fetch_catalog": _boom()})
    namespace["DATA"]["GITHUB_METADATA_NEXT_RETRY_SECONDS"] = 3600

    namespace["update_github_metadata"]()

    assert namespace["DATA"]["GITHUB_METADATA_NEXT_RETRY_SECONDS"] == 3600


def test_a_recovered_fetch_clears_the_backoff():
    namespace = _update_github_metadata_namespace({"get_latest_stable_release": _boom(), "get_github_stars": _boom(), "fetch_catalog": _boom()})
    namespace["update_github_metadata"]()
    assert "GITHUB_METADATA_NEXT_RETRY_SECONDS" in namespace["DATA"]

    namespace["get_latest_stable_release"] = _ok("1.7.0")
    namespace["get_github_stars"] = _ok(42)
    namespace["fetch_catalog"] = _ok(["x"])
    namespace["update_github_metadata"]()

    assert "GITHUB_METADATA_NEXT_RETRY_SECONDS" not in namespace["DATA"]


def test_a_healthy_run_never_warns():
    namespace = _update_github_metadata_namespace({"get_latest_stable_release": _ok("1.7.0"), "get_github_stars": _ok(42), "fetch_catalog": _ok(["x"])})

    namespace["update_github_metadata"]()

    namespace["LOGGER"].warning.assert_not_called()
    assert "GITHUB_METADATA_NEXT_RETRY_SECONDS" not in namespace["DATA"]


# ------------------------------------------------------------------------------------------ gate


def _refresh_gate():
    """The `before_request` `if` block that decides whether to submit `update_github_metadata`."""
    before_request = _function(MAIN, "before_request")
    gate = next(node for node in ast.walk(before_request) if isinstance(node, ast.If) and "LATEST_VERSION_LAST_CHECK" in ast.unparse(node.test))
    function = ast.FunctionDef(
        name="run_gate", args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[gate], decorator_list=[]
    )
    executor = Mock()
    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "DATA": {},
        "_periodic_tasks_executor": executor,
        "update_github_metadata": Mock(),
        "GITHUB_METADATA_REFRESH_SECONDS": 3600,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(MAIN), "exec"), namespace)  # noqa: S102
    return namespace["run_gate"], namespace["DATA"], executor


def test_gate_uses_the_narrowed_backoff_instead_of_the_full_hour():
    run_gate, data, executor = _refresh_gate()
    data["LATEST_VERSION_LAST_CHECK"] = (datetime.now().astimezone() - timedelta(seconds=90)).isoformat()
    data["GITHUB_METADATA_NEXT_RETRY_SECONDS"] = 60  # backed off: due again after 60s, and 90s have passed

    run_gate()

    executor.submit.assert_called_once()


def test_gate_still_waits_out_the_full_hour_when_healthy():
    run_gate, data, executor = _refresh_gate()
    data["LATEST_VERSION_LAST_CHECK"] = (datetime.now().astimezone() - timedelta(seconds=90)).isoformat()

    run_gate()

    executor.submit.assert_not_called()
