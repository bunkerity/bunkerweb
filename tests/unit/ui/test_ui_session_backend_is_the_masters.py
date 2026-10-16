"""Every UI worker takes its session backend from the gunicorn master.

A worker recycled by max_requests used to re-read USE_REDIS on its own. When the pool
disagreed (some workers booted before USE_REDIS=yes was stored, a later one after), sessions written
by one backend were invisible to the others and the user was logged out on every other request.
The master decides once (`on_starting`, before it forks) and publishes it in the environment every
forked or re-forked worker inherits; main.py obeys it.
"""

import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

UI = Path(__file__).resolve().parents[3] / "src" / "ui"
MAIN = UI / "main.py"
GUNICORN = UI / "utils" / "gunicorn.conf.py"


def _choice(env_value, monkeypatch):
    """Run main.py's backend choice (`session_backend` -> `redis_client`) + `if redis_client: ... else: ...` for a worker that now sees USE_REDIS=yes."""
    if env_value is None:
        monkeypatch.delenv("UI_SESSION_BACKEND", raising=False)
    else:
        monkeypatch.setenv("UI_SESSION_BACKEND", env_value)
    tree = ast.parse(MAIN.read_text())
    assign = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "session_backend")
    choice = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and ast.unparse(n.test) == "session_backend == 'filesystem'")
    branch = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Name)
        and n.test.id == "redis_client"
        and any("Using FileSystemCache" in ast.unparse(s) for s in n.orelse)
    )
    redis = object()
    get_ui_redis_client = Mock(return_value=redis)  # what a late-booted worker gets: USE_REDIS is "yes" by now
    app = SimpleNamespace(config={})
    ns = dict(
        app=app,
        LOGGER=Mock(),
        BW_CONFIG=Mock(),
        get_ui_redis_client=get_ui_redis_client,
        getenv=os.getenv,
        getenv_bool=lambda k, d="no": os.getenv(k, d).lower() in ("yes", "true", "1"),
    )
    exec(compile(ast.Module(body=[assign, choice, branch], type_ignores=[]), str(MAIN), "exec"), ns)  # noqa: S102
    return app.config, get_ui_redis_client


def test_a_worker_obeys_the_masters_filesystem_decision(monkeypatch):
    config, get_client = _choice("filesystem", monkeypatch)
    assert config["SESSION_TYPE"] == "cachelib"
    get_client.assert_not_called()


def test_a_worker_obeys_the_masters_redis_decision(monkeypatch):
    config, get_client = _choice("redis", monkeypatch)
    assert config["SESSION_TYPE"] == "redis"
    get_client.assert_called_once_with(master_chose_redis=True)


def test_without_a_master_decision_the_worker_decides_as_before(monkeypatch):
    config, get_client = _choice(None, monkeypatch)
    assert config["SESSION_TYPE"] == "redis"
    get_client.assert_called_once_with()


def test_the_master_publishes_its_decision_before_it_forks():
    fn = next(n for n in ast.parse(GUNICORN.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "on_starting")
    src = ast.unparse(fn)
    assert "environ['UI_SESSION_BACKEND']" in src  # ast.unparse quotes with '
    # after USE_REDIS is read (and after the wait for the scheduler's first configuration)
    assert src.index("_wait_for_first_config(") < src.index("environ['UI_SESSION_BACKEND']")
