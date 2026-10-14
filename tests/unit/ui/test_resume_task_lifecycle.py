"""Real future lifecycle and filesystem marker checks; no runtime stack required."""

import ast
from concurrent.futures import Future, ThreadPoolExecutor
from fcntl import LOCK_EX, LOCK_NB, flock
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

UTILS = Path(__file__).resolve().parents[3] / "src/ui/app/routes/utils.py"


@pytest.fixture
def tasks(tmp_path):
    tree = ast.parse(UTILS.read_text())
    names = {"active_config_tasks", "submit_config_task"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    # Inject the two runtime singletons below, without booting container-only dependencies.
    for node in nodes:
        node.body = [child for child in node.body if not isinstance(child, ast.ImportFrom) or child.module != "app.dependencies"]
    data = type("Data", (dict,), {"load_from_file": lambda self: None})(TO_FLASH=[], CONFIG_CHANGED=True)
    data.file_path = tmp_path / "ui_data.json"
    pending = []

    def submit(task, *args, **kwargs):
        future = Future()
        pending.append((future, task, args, kwargs))
        return future

    namespace = {
        "DATA": data,
        "CONFIG_TASKS_EXECUTOR": Mock(submit=Mock(side_effect=submit)),
        "CONFIG_TASK_TIMEOUT": 60,
        "time": lambda: 100,
        "uuid4": uuid4,
        "flock": flock,
        "LOCK_EX": LOCK_EX,
        "LOCK_NB": LOCK_NB,
        "LOGGER": Mock(),
        "translated": lambda *_args: "localized error",
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(UTILS), "exec"), namespace)
    assert names <= namespace.keys(), "Config tasks currently have no lifecycle tracking"
    return SimpleNamespace(ns=namespace, data=data, pending=pending, directory=tmp_path / "config_tasks")


def complete(entry, error=None):
    future, task, args, kwargs = entry
    if error:
        future.set_exception(error)
    else:
        future.set_result(task(*args, **kwargs))


def test_overlapping_tasks_keep_the_remaining_task_active(tasks):
    for _ in range(2):
        tasks.ns["submit_config_task"](lambda: None)
    assert tasks.ns["active_config_tasks"]() == 2
    complete(tasks.pending[0])
    assert tasks.data["RELOADING"] is True
    assert tasks.ns["active_config_tasks"]() == 1
    complete(tasks.pending[1])
    assert tasks.data["RELOADING"] is False
    assert tasks.ns["active_config_tasks"]() == 0


def test_failed_task_is_reported_and_marker_is_removed(tasks):
    tasks.ns["submit_config_task"](lambda: None)
    complete(tasks.pending[0], RuntimeError("unexpected"))
    assert tasks.data["TO_FLASH"] == [{"content": "localized error", "type": "error"}]
    assert tasks.data["RELOADING"] is False
    assert not list(tasks.directory.iterdir())
    tasks.ns["LOGGER"].exception.assert_called_once()


def test_submission_failure_does_not_release_other_work(tasks):
    tasks.ns["submit_config_task"](lambda: None)
    tasks.ns["CONFIG_TASKS_EXECUTOR"].submit.side_effect = RuntimeError("shutdown")
    with pytest.raises(RuntimeError, match="shutdown"):
        tasks.ns["submit_config_task"](lambda: None)
    assert tasks.data["RELOADING"] is True
    assert tasks.ns["active_config_tasks"]() == 1
    complete(tasks.pending[0])
    assert tasks.ns["active_config_tasks"]() == 0


def test_stale_unlocked_marker_expires_but_live_queued_work_does_not(tasks):
    tasks.ns["submit_config_task"](lambda: None)
    stale = tasks.directory / "abandoned"
    stale.touch()
    tasks.ns["time"] = lambda: stale.stat().st_mtime + 61
    assert tasks.ns["active_config_tasks"]() == 1
    assert not stale.exists()
    complete(tasks.pending[0])


def test_shared_executor_is_retained_and_keyword_arguments_reach_task(tasks):
    with ThreadPoolExecutor(max_workers=1) as executor:
        tasks.ns["CONFIG_TASKS_EXECUTOR"] = executor
        future = tasks.ns["submit_config_task"](lambda *, value: value, value="0")
        assert future.result(timeout=5) == "0"
    assert tasks.data["RELOADING"] is False
    assert not list(tasks.directory.iterdir())


def test_cancelled_future_releases_queued_marker(tasks):
    future = tasks.ns["submit_config_task"](lambda: None)
    assert future.cancel()
    assert tasks.data["RELOADING"] is False
    assert tasks.ns["active_config_tasks"]() == 0


def test_marker_lock_is_visible_across_workers_and_released_on_exit(tasks):
    tasks.directory.mkdir()
    marker = tasks.directory / "other-worker"
    script = "from fcntl import flock, LOCK_EX; import sys; f=open(sys.argv[1], 'w'); flock(f, LOCK_EX); print('ready', flush=True); sys.stdin.read()"
    process = subprocess.Popen([sys.executable, "-c", script, str(marker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        expired_at = marker.stat().st_mtime + 61
        tasks.ns["time"] = lambda: expired_at
        assert tasks.ns["active_config_tasks"]() == 1
        process.communicate(timeout=5)
        assert tasks.ns["active_config_tasks"]() == 0
        assert not marker.exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def test_every_route_configuration_submission_uses_lifecycle_wrapper():
    routes = UTILS.parent
    direct = []
    for path in routes.glob("*.py"):
        if path == UTILS:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "CONFIG_TASKS_EXECUTOR.submit":
                direct.append(f"{path.name}:{node.lineno}")
    assert not direct, direct
